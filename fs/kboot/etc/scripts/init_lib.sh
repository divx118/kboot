#!/bin/sh
# init_lib.sh : 21/01/10
# g.revaillot, revaillot@archos.com

log()
{
	if [ $verbose -ne 0 ]; then
		echo $* 1>&2
	fi
}

log_and_die()
{
	log "die."
	log $*

	umount_a

	while true; do sleep 1; done
}

log_and_reboot()
{
	log "reboot."
	log $*

	umount_a

	/sbin/reboot -f
	while true; do sleep 1; done
}

log_and_shutdown()
{
	log "shutdown."
	log $*

	umount_a

	/sbin/poweroff
	while true; do sleep 1; done
}

# misc
display_banner()
{
	product=$1
	revision=$2

	$ZCAT /mnt/rawfs/banner | $FB_WRITE

	$RFBI_REFRESH

	echo 255 > /sys/class/leds/lcd-backlight/brightness
}

# device related

set_charger_state()
{
	charger_sysfs="/sys/devices/platform/battery/charge_level"

	# megadroid charge only via dc in..
	if [ -e $charger_sysfs ] ; then
		case $1 in
			"stop") echo 0 > $charger_sysfs ;;
			"lo") echo 1 > $charger_sysfs ;;
			"hi") echo 2 > $charger_sysfs ;;
			"full") echo 3 > $charger_sysfs ;;
		esac
	fi
}

wait_block_devices()
{
	bdevice=$1
	wait_counter=10

	blkdev=/sys/block/`get_mountpoint_blockdev $bdevice`
	while [  $wait_counter -gt 0 ] ; do
		if [ -d $blkdev ]; then
			break
		fi
		sleep 1
		let wait_counter-=1
	done

	if [ $wait_counter -eq 0 ] ; then
		return 1
	fi

	return 0;
}

wait_for_std_block_devices()
{
	for bdevice in rawfs storage; do
		wait_block_devices $bdevice
		if [ $? -eq 1 ] ; then
			return 1
		fi
	done

	return 0
}

# fs related
get_mount_info()
{
	info=$1 # asked information
	mount_name=$2 # mount_point pseudo name

	mptab="/etc/mountpoints"

	# search for some device-specific mount point
	special_name_dev="$mount_name"_`$GET_INFO p`
	if [ `grep "^$special_name_dev\b" $mptab | wc -l` != 0 ] ; then
		mount_name=$special_name_dev
	fi

	case $info in
		d) echo `grep "^$mount_name\b" $mptab | cut -f2` ;;	# mount device
		p) echo `grep "^$mount_name\b" $mptab | cut -f3` ;;	# mount point

		f) _fs="`grep "^$mount_name\b" $mptab | cut -f4`"	# mount filesystem
			case $_fs in
				"#storage_fs#") echo `$GET_STORAGE_PROP get` ;;
				*) echo $_fs  ;;
			esac ;;

		o) _op="`grep "^$mount_name\b" $mptab | cut -f5`"	# mount options
			case $_op in
				"#storage_opt#") echo `$GET_STORAGE_PROP get_opt` ;;
				*) echo $_op  ;;
			esac ;;

		n) _nm="`grep "^$mount_name\b" $mptab | cut -f6`"	# mount volume name
			case $_nm in
				"#storage_name#") echo `$GET_INFO l` ;;
				"#ramdisk_name#") echo `$GET_INFO l`_REC ;;
				*) echo $_nm  ;;
			esac ;;

		e) echo `grep "^$mount_name\b" $mptab | cut -f7` ;;	# mount error code
	esac
}

get_mountpoint_blockdev()
{
	mountmoint=$1
	dev=`get_mount_info d $mountmoint`

	echo `partdev2blockdev $dev`
}

partdev2blockdev()
{
	partdev=`echo $1 | cut -d'/' -f3`
	bkldev=""

	if [ "`echo $partdev | cut -c -2 `" = "sd" ] ; then
		blkdev=`echo $partdev | cut -c -3`
	elif [ "`echo $partdev | cut -c -4 `" = "loop" ] ; then
		blkdev="ram0"
	else
		blkdev=`echo $partdev | cut -c -7`
	fi

	echo "$blkdev"
}

umount_properly_partition()
{
	mount_point=$1 # $1 : mount_point to umount
	umount_count=5
	while [ $umount_count -gt 0 ]; do
		$UMOUNT $mount_point > /dev/null 2>&1

		if [ "`mount | grep "\b$mount_point\b"`" == "" ] ; then
			return;
		fi

		sleep 1
		let umount_count-=1
	done

	$UMOUNT -f $mount_point

	return $?
}

umount_p()
{
	mount_point_name=$1

	log "umount_p $mount_point_name"

	mount_point=`get_mount_info p $mount_point_name`

	if [ $mount_point = "-" ] ; then
		log "umounting $mount_point_name skipped."
		return 0
	fi

	umount_properly_partition  $mount_point

	return $?
}

mount_p()
{
	mount_point_name=$1
	alt_mount_options=$2

	log "mount_p $mount_point_name"

	mount_dev=`get_mount_info d $mount_point_name`
	mount_fs=`get_mount_info f $mount_point_name`
	mount_options=`get_mount_info o $mount_point_name`
	mount_point=`get_mount_info p $mount_point_name`
	mount_errorcode=`get_mount_info e $mount_point_name`

	if [ $mount_point = "-" ] ; then
		log "mounting $mount_point_name skipped."
		return 0
	fi

	mkdir -p $mount_point

	$MOUNT -t $mount_fs -o $mount_options $mount_dev $mount_point
	ret=$?

	if [ $ret -ne 0 ] ; then
		log "mounting $mount_point_name partition failed ($ret)"
		RECOVERY_ERROR_CODE=$mount_errorcode
	else
		log "mount $mount_point_name ok"
	fi

	return $ret
}

umount_a()
{
	sync
	
	for mount_entry in `cat /proc/mounts | \
		cut -d\  -f2 | \
		grep -v "^/proc$" | \
		grep -v "^/$" `; do \
		umount_properly_partition $mount_entry
	done
}

_async_run()
{
	funct=$1
	ret_path=$2

	$funct
	ret=$?

	echo $ret > $ret_path
}

# run anything asynchronous, with a timeout.
run_async()
{
	funct=$1
	timeout=$2
	ret_path="/tmp/"$RANDOM"_"$funct"_return"

	_async_run $funct $ret_path &
	aspid=$!

	log "launched $funct ($aspid)"

	# no ps -p in kr, nor cut/sed/awk :
	# grep for process the dirty way..
	cnt=0
	while [ "`ps | grep "^\s*$aspid\s*"`" ] ; do\
		let cnt=$cnt+1
		sleep 1
		if [ $cnt -gt $timeout ] ; then \
			kill $aspid
			log "$funct killed by init: too long."
			break
		fi
	done

	if [ -e $ret_path ] ; then \
		return `cat $ret_path`
	fi

	# something went wrong.
	return 255
}

# EOF

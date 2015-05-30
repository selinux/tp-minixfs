# -*- coding: utf-8 -*-
# Note : minix-fs types are little endian


__author__ = 'Sebastien Chassot'
__author_email__ = 'sebastien.chassot@etu.hesge.ch'

__version__ = "1.0.1"
__copyright__ = ""
__licence__ = ""
__status__ = "TP minix fs"

from minix_inode import *
from bloc_device import *


class minix_file_system(object):
    def __init__(self, fs_src=None, port=None):
        if( fs_src and port ):
            self.disk = remote_bloc_device(BLOCK_SIZE, fs_src, port)
        else:
            self.disk = bloc_device(BLOCK_SIZE, fs_src)

        self.inode_map = bitarray(endian='little')
        self.zone_map = bitarray(endian='little')
        self.inode_map.frombytes(self.disk.read_bloc(2, self.disk.super_block.s_imap_blocks))
        self.zone_map.frombytes(self.disk.read_bloc(2 + self.disk.super_block.s_imap_blocks,
                                                  self.disk.super_block.s_zmap_blocks))

        # initialising the list by an unused inode (inode start at indices 1)
        self.inodes_list = [minix_inode()]
        buff = self.disk.read_bloc(2 + self.disk.super_block.s_imap_blocks +
                                 self.disk.super_block.s_zmap_blocks,
                                 self.disk.super_block.s_ninodes / MINIX_INODE_PER_BLOCK)

        for nb in range(self.disk.super_block.s_ninodes):
            i = minix_inode()
            i.i_ino = nb + 1
            s = struct.unpack_from('HHIIBBHHHHHHHHH', buff, nb * INODE_SIZE)
            i.i_zone = list(s[6:13])
            i.i_mode, i.i_uid, i.i_size, i.i_time, i.i_gid, i.i_nlinks = s[0:6]
            i.i_indir_zone = s[13]
            i.i_dbl_indr_zone = s[14]

            self.inodes_list.append(i)

    def ialloc(self):
        """ return the first free inode number available
            starting at 0 and upto s.n_inodes-1.
            The bitmap ranges from index 0 to inod_num-1
            Inode 0 is never and is always set.
            according to the inodes bitmap
        :return: the first free inode
        """
        # TODO add index to inode map and modify inode table
        # TODO call bmap if allowed
        pos = self.inode_map.index(False)

        self.inode_map[pos] = True
        self.inodes_list.pop(pos)  # clear
        self.inodes_list.insert(pos, minix_inode())  # insert new empty inode

        return int(pos)

    def ifree(self, inodnum):
        """ toggle an inode as available for the next ialloc()
        :param inodnum:
        :return: True if inodnum == False
        """
        # inodes start at 1
        self.inode_map[inodnum] = False
        return ~self.inode_map[inodnum]  # return 'not' state (true if false)

    def balloc(self):
        """ return the first free bloc index in the volume.
        :return: the first free bloc
        """
        try:
            pos = self.zone_map.index(False)
        except ValueError:
            sys.exit('Error no space left on device')

        self.zone_map[pos] = True

        # data block start at 1
        return int(pos + self.disk.super_block.s_firstdatazone)

    def bfree(self, blocnum):
        """ toggle a bloc as available for the next balloc()
        :param blocnum: blocnum is an index in the zone_map
        :return: True if bloc is free
        """
        self.zone_map[blocnum] = False

        return ~self.zone_map[blocnum]

    def bmap(self, inode, blk):
        """ Map a block number with his real block number on disk

        :param inode: the inode
        :param blk: the block number ( 0,.., n-1)
        :return: the corresponding block number on disk
        """
        # direct blocks
        if blk < 7:
            return inode.i_zone[blk]

        blk -= 7

        # indirect blocks
        if blk < MINIX_ZONESZ:
            return int(struct.unpack_from('H', self.disk.read_bloc(inode.i_indir_zone), blk*2)[0])

        blk -= MINIX_ZONESZ

        # double indirect blocks
        if blk < MINIX_ZONESZ**2:
            indir = blk / BLOCK_SIZE # indirect bloc addr
            off = blk % MINIX_ZONESZ

            # read the second indirect block + read 'indirect' address and return 'offset' address
            return int(struct.unpack_from('H', self.disk.read_bloc(struct.unpack_from(
                                          'H', self.disk.read_bloc(inode.i_dbl_indr_zone), indir*2)[0]), off*2)[0])

        else:
            log.error('Error bmap, block is out of bound')
            raise OutboundError('Error Block is out of bound')

    def lookup_entry(self, dinode, name):
        """ lookup for a name in a directory, and return its inode number,
            given inode directory dinode
        :param dinode: directory inode
        :param name: dirname to search
        :return: directory's inode
        """
        blk = 0
        data_block = self.bmap(dinode, blk)
        d_entry = {}

        while data_block:
            content = self.disk.read_bloc(data_block)
            for off in xrange(0, BLOCK_SIZE, DIRSIZE):
                self.inode = struct.unpack_from('H', content, off)[0]
                self.name = content[off+2:off+DIRSIZE].split('\x00')[0]
                if self.inode != 0:
                    # add entry to dictionary
                    d_entry.update({self.name: self.inode})

            # pick next data block
            blk += 1
            data_block = self.bmap(dinode, blk)

        # return name in dict (raise error if not fund)
        return d_entry[name]

    def namei(self, path):
        """  take a path as input and return it's inode number

        :param path: path to search
        :return: inode of the file
        """
        self.path = path[1:].split('/')
        self.inode = 1

        # if path empty it's root. So return inode = 1
        if not self.path[0]:
            return self.inode

        # TODO add raise exception in lookup_entry
        for i in self.path:
            try:
                self.inode = self.lookup_entry(self.inodes_list[self.inode], i)

            except KeyError:
                log.error('Error lookup_entry, '+os.strerror(errno.ENODEV))
                raise FileNotFoundError('Error file not found')

        return self.inode

    def ialloc_bloc(self, inode, blk):
        """ Add a new data block at pos blk and return its real position on disk

        :param inode: the inode to add at
        :param blk: the block number to add (0,...,n-1)
        :return: the block address
        """
        if blk < 7:
            if not inode.i_zone[blk]:
                inode.i_zone[blk] = self.balloc()
            return inode.i_zone[blk]

        elif blk < MINIX_INODE_PER_BLOCK + 7:
            # if not already allowed write modified indirect block
            if not struct.unpack_from('H', self.disk.read_bloc(inode.i_zone[7]), blk - 7):
                self.disk.write_bloc(2+self.disk.super_block.s_imap_blocks,
                                   struct.pack_into('H', self.disk.read_bloc(inode.i_zone[7], blk - 7), blk - 7,
                                                    self.balloc()))
            # now we can return it
            return struct.unpack_from('H', self.disk.read_bloc(inode.i_zone[7]), blk - 7)

        else:
            # if not already allowed write modified second indirect block
            if not struct.unpack_from('H', self.disk.read_bloc(inode.i_zone[8]), blk - 7 - MINIX_INODE_PER_BLOCK):
                self.disk.write_bloc(2+self.disk.super_block.s_imap_blocks, struct.pack_into('H', self.disk.read_bloc(inode.i_zone[8],
                                                    blk - 7 - MINIX_INODE_PER_BLOCK),
                                                    blk - 7 - MINIX_INODE_PER_BLOCK, self.balloc()))
            # now we can return it
            return struct.unpack_from('H', self.disk.read_bloc(inode.i_zone[8]), blk - 7 - MINIX_INODE_PER_BLOCK)


    def add_entry(self, dinode, name, new_node_num):
        """ add a new entry in a dinode (dir)

        :param dinode: inode number of the dir
        :param name: name of the file to be added
        :param new_node_num: inode of the new file
        """
        done = False
        blk = -1

        if len(name) > (DIRSIZE-2): raise FileNameError('Error Filename too long')
        if self.lookup_entry(dinode, name):
            raise AddEntryError('Error filename already exist in dir')

        while not done:

            blk += 1
            data_block = self.bmap(dinode, blk)

            if data_block:
                self.content = bytearray(self.disk.read_bloc(data_block))

            elif blk < MINIX_ZONESZ**2 + MINIX_ZONESZ + 7:
                data_block = self.ialloc_bloc(dinode, blk)
                # empty new block
                self.content = bytearray("".ljust(1024, '\x00'))

            else:
                log.error('Error unable to add new entry in dir: overflow')
                raise DirFullError('Error too many file in dir: overflow')

            for off in xrange(0, BLOCK_SIZE, DIRSIZE):
                if not struct.unpack_from('H', self.content, off)[0]:
                    struct.pack_into('H', self.content, off, new_node_num)
                    self.content[off+2:off+DIRSIZE] = name.ljust(DIRSIZE-2, '\x00')
                    dinode.i_size += DIRSIZE
                    done = True
                    break

        if done:
            self.disk.write_bloc(data_block, self.content)
        else:
            log.error('Error unable to add new entry in dir')
            raise AddError('Unable to add entry')

    def del_entry(self, dinode, name):
        """ delete filename from dir

        :param dinode: the directory's file
        :param name: filename to remove
        """
        blk = -1
        inode = self.lookup_entry(dinode, name)
        if not self.ifree(inode):
            raise DelEntryError('Error deleting entry filename not found')

        dir_block = 1

        # while dir block search inode
        while dir_block:
            blk += 1
            dir_block = self.bmap(dinode, blk)
            # take a block
            dir_content = bytearray(self.disk.read_bloc(dir_block))

            # look for inode
            for i in xrange(0, BLOCK_SIZE, DIRSIZE):
                if inode == struct.unpack_from('H', dir_content, i)[0]:
                    # remove entry
                    # dir_content[i:i+DIRSIZE] = "".ljust(DIRSIZE, '\x00')
                    dir_content[i:i+2] = "".ljust(2, '\x00')
                    self.bfree(dir_block)
                    if self.inodes_list[inode].i_nlinks > 1:
                        # inode has another name linked to it
                        self.inodes_list[inode].i_nlinks -= 1
                    else:
                        fb = 0
                        file_blk = self.bmap(self.inodes_list[inode], fb)
                        # free file's data block
                        while file_blk:
                            self.bfree(file_blk)
                            fb += 1
                            file_blk = self.bmap(self.inodes_list[inode], fb)

                        self.ifree(inode)
                    dir_block = False
                    dinode.i_size -= DIRSIZE
                    break

            if dir_content == "".ljust(BLOCK_SIZE, '\x00'):
                # TODO replace by remove dir_block from dinode ou write_bloc
                self.bfree(dir_block)

        self.disk.write_bloc(dinode.i_zone[blk], dir_content)

    def update_imap(self):
        """ Write bitarray and inodes_list to disk
            cos we need a consistent filesystem
        :return: 0
        """
        offset = 2
        # Write can only handle 1024 byte so need to slice (just in case)
        for i in range(self.disk.super_block.s_imap_blocks):
            # write inode bitmap starting at bloc 2
            self.disk.write_bloc(offset+i, self.inode_map[i*(8*BLOCK_SIZE):(i+1)*(8*BLOCK_SIZE)-1].tobytes())

        return 0

    def update_bmap(self):
        """ Write bitarray map of data to disk
            cos we need a consistent filesystem
        :return: 0
        """
        offset = 2 + self.disk.super_block.s_imap_blocks
        # Write can only handle 1024 byte so need to slice (just in case)
        for i in range(self.disk.super_block.s_zmap_blocks):
            # write inode bitmap starting at bloc 2
            self.disk.write_bloc(offset+i, self.inode_map[i*(8*BLOCK_SIZE):(i+1)*(8*BLOCK_SIZE)-1].tobytes())

        return 0

    def write_bloc_list(self):

        for i in range(self.disk.super_block.s_zmap_blocks):
            # start at bloc 2
            self.disk.write_bloc(2 + self.disk.super_block.s_imap_blocks + i, \
                               self.zone_map.tobytes()[i * BLOCK_SIZE:(i + 1) * BLOCK_SIZE])
        return

    def close_connection(self):
        log.info("socket cleanly closed")
        self.disk.close_connection()

    def is_dir(self, inode):
        """ Test if inode is a dir
        :param inode:
        :return: True if inode is a dir
        """
        return True if (self.inodes_list[self.inode].i_mode >> 12) == 4 else False

    def is_file(self, inode):
        """ Test if inode is a file
        :param inode:
        :return: True if inode is a file
        """
        return True if (self.inodes_list[self.inode].i_mode >> 12) == 8 else False

    def is_device(self, inode):
        """ Test if inode is a device
        :param inode:
        :return: True if inode is a device
        """
        return True if (self.inodes_list[self.inode].i_mode >> 12) == 2 else False

    def is_pipe(self, inode):
        """ Test if inode is a pipe
        :param inode:
        :return: True if inode is a pipe
        """
        return True if (self.inodes_list[self.inode].i_mode >> 12) == 1 else False

    def is_device_bloc(self, inode):
        """ Test if inode is a device bloc
        :param inode:
        :return: True if inode is a device block
        """
        return True if (self.inodes_list[self.inode].i_mode >> 12) == 6 else False

    def is_link(self, inode):
        """ Test if inode is a device link
        :param inode:
        :return: True if inode is a link
        """
        return True if (self.inodes_list[self.inode].i_mode >> 12) == 10 else False


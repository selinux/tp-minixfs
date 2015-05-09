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
    def __init__(self, filename):
        self.disk = bloc_device(BLOCK_SIZE, filename)
        self.disk1 = remote_bloc_device(BLOCK_SIZE, 'localhost', 1234)

        self.inode_map = bitarray(endian='little')
        self.zone_map = bitarray(endian='little')
        self.inode_map.frombytes(self.disk.read_bloc(2, numofblk=self.disk.super_block.s_imap_blocks))
        self.zone_map.frombytes(self.disk.read_bloc(2 + self.disk.super_block.s_imap_blocks,
                                                  numofblk=self.disk.super_block.s_zmap_blocks))

        # initialising the list by an unused inode (inode start at indices 1)
        self.inodes_list = [minix_inode(num=0, mode=0, uid=0, size=0, time=0, gid=0, nlinks=0,
                                        zone=[], indir_zone=0, dblr_indir_zone=0)]
        buff = self.disk.read_bloc(2 + self.disk.super_block.s_imap_blocks +
                                 self.disk.super_block.s_zmap_blocks,
                                 numofblk=self.disk.super_block.s_ninodes / MINIX_INODE_PER_BLOCK)

        for nb in range(self.disk.super_block.s_ninodes):
            i = minix_inode()
            i.i_ino = nb + 1
            if self.inode_map[nb]:
                s = struct.unpack_from('HHIIBBHHHHHHHHH', buff, nb * 32)
                i.i_zone = list(s[6:13])
                i.i_mode, i.i_uid, i.i_size, i.i_time, i.i_gid, i.i_nlinks = s[0:6]
                i.i_indir_zone = s[13]
                i.i_dbl_indr_zone = s[14]

            self.inodes_list.append(i)

        self.disk1.write_block(2, "Datas to be transmitted")
        #self.disk1.read_block(1)

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

        self.update_imap()

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
        self.update_bmap()
        # data block start at 1
        return int(pos + self.disk.super_block.s_firstdatazone)

    def bfree(self, blocnum):
        """ toggle a bloc as available for the next balloc()
        :param blocnum: blocnum is an index in the zone_map
        :return: True if bloc is free
        """
        # data block start at 1 with an offset of first data bloc
        # blocnum = blocnum - self.bd.super_block.s_firstdatazone
        self.zone_map[blocnum] = False
        self.update_bmap()

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

        # indirect blocks
        elif blk < ((BLOCK_SIZE/2) + 7):
            return int(struct.unpack_from('H', self.disk.read_bloc(inode.i_indir_zone), (blk - 7)*2)[0])

        # double indirect blocks
        elif (blk < (MINIX_INODE_PER_BLOCK + 1) * MINIX_INODE_PER_BLOCK + 7):
            indir = (blk - 7 - (BLOCK_SIZE/2)) / BLOCK_SIZE # indirect bloc addr
            off = blk - 7 - (BLOCK_SIZE/2)

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
            # TODO replace range by xrange 0 1024 16
            for i in range(MINIX_DIR_ENTRIES_PER_BLOCK):
                off = i * DIRSIZE
                self.inode = struct.unpack_from('H', content, i*DIRSIZE)[0]
                self.name = content[off+2:off+DIRSIZE].split('\x00')[0]
                if self.inode != 0:
                    # add entry to dictionary
                    d_entry.update({self.name: self.inode})

            # pick next data block
            blk += 1
            data_block = self.bmap(dinode, blk)

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
                # if __debug__: print(self.inode.__str__())
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


    # TODO add a dinode if dir is full
    def add_entry(self, dinode, name, new_node_num):
        """ add a new entry in a dinode (dir)

        :param dinode: inode number of the dir
        :param name: name of the file to be added
        :param new_node_num: inode of the new file
        """
        done = False
        block = -1

        # TODO update link
        # TODO update file size
        if len(name) > (DIRSIZE-2): raise FileNameError('Error Filename too long')

        while not done:

            block += 1
            data_block = self.bmap(dinode, block)

            # TODO increase dir capacity with indir and double indir
            if data_block:
                content = bytearray(self.disk.read_bloc(data_block))
            else:
                if data_block < 7:
                    dinode.i_zone[data_block+1] = self.balloc()
                else:
                    log.error('Error unable to add new entry in dir')
                    raise DirFullError('Error too many file in dir')

                content = bytearray("".ljust(1024, '\x00'))

            for offset in xrange(0, BLOCK_SIZE, DIRSIZE):
                if not struct.unpack_from('H', content, offset)[0]:
                    struct.pack_into('H', content, offset, new_node_num-1)
                    content[offset+2:offset+DIRSIZE] = name.ljust(DIRSIZE-2, '\x00')
                    dinode.i_size += DIRSIZE
                    done = True
                    break

        if done:
            self.disk.write_bloc(dinode.i_zone[block], content)
            self.update_imap()
        else:
            log.error('Error unable to add new entry in dir')
            raise AddError('Unable to add entry')

    #delete an entry named "name" 
    def del_entry(self, dinode, name):
        blk = -1
        inode = self.lookup_entry(dinode, name)
        if not self.ifree(inode):
            raise DelEntryError('Error deleting entry')

        data_block = 1

        while data_block:
            blk += 1
            data_block = self.bmap(dinode, blk)
            content = bytearray(self.disk.read_bloc(data_block))
            for i in xrange(0, BLOCK_SIZE, DIRSIZE):
                # remove entry
                if inode == struct.unpack_from('H', content, i)[0]:
                    content[i:i+2] = "".ljust(2, '\x00')
                    self.bfree(data_block)
                    data_block = 0
                    dinode.i_size -= DIRSIZE
                    self.update_bmap()
                    self.update_imap()
                    break

        self.disk.write_bloc(dinode.i_zone[blk], content)


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


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
        self.bd = bloc_device(BLOCK_SIZE, filename)

        self.inode_map = bitarray(endian='little')
        self.zone_map = bitarray(endian='little')
        self.inode_map.frombytes(self.bd.read_bloc(2, numofblk=self.bd.super_block.s_imap_blocks))
        self.zone_map.frombytes(self.bd.read_bloc(2 + self.bd.super_block.s_imap_blocks,
                                                  numofblk=self.bd.super_block.s_zmap_blocks))

        self.inodes_list = [minix_inode(num=0, mode=0, uid=0, size=0, time=0, gid=0, nlinks=0,
                                        zone=[], indir_zone=0, dblr_indir_zone=0)]
        buff = self.bd.read_bloc(2 + self.bd.super_block.s_imap_blocks +
                                 self.bd.super_block.s_zmap_blocks,
                                 numofblk=self.bd.super_block.s_ninodes / MINIX_INODE_PER_BLOCK)

        for nb in range(self.bd.super_block.s_ninodes):
            i = minix_inode()
            i.i_ino = nb + 1
            if self.inode_map[nb]:
                s = struct.unpack_from('HHIIBBHHHHHHHHH', buff, nb * 32)
                i.i_zone = list(s[6:13])
                i.i_mode, i.i_uid, i.i_size, i.i_time, i.i_gid, i.i_nlinks = s[0:6]
                i.i_indir_zone = s[13]
                i.i_dbl_indr_zone = s[14]

            self.inodes_list.append(i)
            del i

            # print(self.inodes_list[167])

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
        return ~self.inode_map[inodnum]

    def balloc(self):
        """ return the first free bloc index in the volume.
        :return: the first free bloc
        """
        pos = self.zone_map.index(False)
        self.zone_map[pos] = True
        self.update_bmap()
        # data block start at 1
        return int(pos + self.bd.super_block.s_firstdatazone)

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
        if blk < 7:
            return inode.i_zone[blk]

        elif blk < (MINIX_INODE_PER_BLOCK + 7):
            # print(struct.unpack_from('H', self.bd.read_bloc(inode.i_indir_zone), blk - 7).__str__())
            return int(struct.unpack_from('H', self.bd.read_bloc(inode.i_indir_zone), blk - 7)[0])

        # TODO correct double indirection 512^2
        # TODO elif blk < 513*512+7  sinon rise error
        elif (blk < (MINIX_INODE_PER_BLOCK + 1) * MINIX_INODE_PER_BLOCK + 7):
            indir = (blk - 7 - MINIX_INODE_PER_BLOCK) / MINIX_INODE_PER_BLOCK # indirect bloc addr
            off = (blk - 7 - MINIX_INODE_PER_BLOCK) % MINIX_INODE_PER_BLOCK

            # read the second indirect block + read 'indirect' address and return 'offset' address
            return int(struct.unpack_from('H',
                                           self.bd.read_bloc(struct.unpack_from('H',
                                           self.bd.read_bloc(inode.i_dbl_indr_zone), indir)[0]), off)[0])
        else:
            return -1

    def lookup_entry(self, dinode, name):
        """ lookup for a name in a directory, and return its inode number,
            given inode directory dinode
        :param dinode: directory inode
        :param name: dirname to search
        :return: directory's inode
        """
        # TODO use bmap on each dir (be sure to look at every block)
        return

    # TODO search directory and file
    #find an inode number according to its path
    #ex : '/usr/bin/cat'
    #only works with absolute paths

    def namei(self, path):
        return

    def ialloc_bloc(self, inode, blk):
        """ Add a new data block at pos blk and return its real position on disk

        :param inode: the inode to add at
        :param blk: the block number to add (0,...,n-1)
        :return: the block address
        """
        if blk < 7:
            if not inode.zone[blk]:
                inode.zone[blk] = self.balloc()
            return inode.zone[blk]

        elif blk < MINIX_INODE_PER_BLOCK + 7:
            # if not already allowed write modified indirect block
            if not struct.unpack_from('H', self.bd.read_bloc(inode.zone[7]), blk - 7):
                self.bd.write_bloc(2+self.bd.super_block.s_imap_blocks,
                                   struct.pack_into('H', self.bd.read_bloc(inode.zone[7], blk - 7), blk - 7,
                                                    self.balloc()))
            # now we can return it
            return struct.unpack_from('H', self.bd.read_bloc(inode.zone[7]), blk - 7)

        else:
            # if not already allowed write modified second indirect block
            if not struct.unpack_from('H', self.bd.read_bloc(inode.zone[8]), blk - 7 - MINIX_INODE_PER_BLOCK):
                self.bd.write_bloc(2+self.bd.super_block.s_imap_blocks, struct.pack_into('H', self.bd.read_bloc(inode.zone[8],
                                                    blk - 7 - MINIX_INODE_PER_BLOCK),
                                                    blk - 7 - MINIX_INODE_PER_BLOCK, self.balloc()))
            # now we can return it
            return struct.unpack_from('H', self.bd.read_bloc(inode.zone[8]), blk - 7 - MINIX_INODE_PER_BLOCK)

    # TODO insert filename in dinode

    # TODO add a dinode if dir is full
    #create a new entry in the node
    #name is an unicode string
    #parameters : directory inode, name, inode number
    def add_entry(self, dinode, name, new_node_num):
        return

    #delete an entry named "name" 
    def del_entry(self, inode, name):
        return

    def update_imap(self):
        """ Write bitarray and inodes_list to disk
            cos we need a consistent filesystem
        :return: 0
        """
        offset = 2
        # Write can only handle 1024 byte so need to slice (just in case)
        for i in range(self.bd.super_block.s_imap_blocks):
            # write inode bitmap starting at bloc 2
            self.bd.write_bloc(offset+i, self.inode_map[i*(8*BLOCK_SIZE):(i+1)*(8*BLOCK_SIZE)-1].tobytes())

        return 0

    def update_bmap(self):
        """ Write bitarray map of data to disk
            cos we need a consistent filesystem
        :return: 0
        """
        offset = 2 + self.bd.super_block.s_imap_blocks
        # Write can only handle 1024 byte so need to slice (just in case)
        for i in range(self.bd.super_block.s_zmap_blocks):
            # write inode bitmap starting at bloc 2
            self.bd.write_bloc(offset+i, self.inode_map[i*(8*BLOCK_SIZE):(i+1)*(8*BLOCK_SIZE)-1].tobytes())

        return 0

    def write_bloc_list(self):

        for i in range(self.bd.super_block.s_zmap_blocks):
            # start at bloc 2
            self.bd.write_bloc(2 + self.bd.super_block.s_imap_blocks + i, \
                               self.zone_map.tobytes()[i * BLOCK_SIZE:(i + 1) * BLOCK_SIZE])
        return

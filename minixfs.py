# -*- coding: utf-8 -*-
#Note : minix-fs types are little endian


__author__ = 'Sebastien Chassot'
__author_email__ = 'sebastien.chassot@etu.hesge.ch'

__version__ = "1.0.1"
__copyright__ = ""
__licence__ = ""
__status__ = "TP minix fs"

from constantes import *
from minix_inode import *
from minix_superbloc import *
from bloc_device import *

class minix_file_system(object):

    def __init__(self, filename):
        self.bd = bloc_device(BLOCK_SIZE, filename)

        self.inode_map = bitarray(bytearray(self.db.read_block(2), self.bd.super_block.s_ninodes))
        self.zone_map = bitarray((bytearray(self.db.read_block(2 + self.bd.super_block.s_ninodes), \
                                  self.db.super_block.s_zmap_blocks)))

    def ialloc(self):
        """ return the first free inode number available
            starting at 0 and upto s.n_inodes-1.
            The bitmap ranges from index 0 to inod_num-1
            Inode 0 is never and is always set.
            according to the inodes bitmap
        :return: the first free inode
        """
        return self.inode_map.index(False)

    # TODO choose the first inode number 0 or 1 do we return inode-1 and read inode+1 -- same problem for zones ??

    def ifree(self, inodnum):
        """ toggle an inode as available for the next ialloc()
        :param inodnum:
        :return: True if inodnum == False
        """
        self.inode_map[inodnum] = False
        return ~self.inode_map[inodnum]

    def balloc(self):
        """ return the first free bloc index in the volume.
        :return: the first free bloc
        """
        return self.zone_map.index(False)
    
    def bfree(self, blocnum):
        """ toggle a bloc as available for the next balloc()
        :param blocnum: blocnum is an index in the zone_map
        :return:
        """
        self.zone_map[blocnum] = False
        return ~self.zone_map[blocnum]
    
    def bmap(self, inode, blk):
        return
    
    def lookup_entry(self, dinode, name):
        """ lookup for a name in a directory, and return its inode number,
            given inode directory dinode
        :param dinode: directory inode
        :param name: dirname to search
        :return: directory's inode
        """
        return

    # TODO search directory and file
    #find an inode number according to its path
    #ex : '/usr/bin/cat'
    #only works with absolute paths
                   
    def namei(self, path):
        return
    
    def ialloc_bloc(self, inode, blk):
        return

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



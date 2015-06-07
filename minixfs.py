# -*- coding: utf-8 -*-

""" This is the main minixfs API """


__author__ = 'Sebastien Chassot'
__author_email__ = 'sebastien.chassot@etu.hesge.ch'

__version__ = "1.0.1"
__copyright__ = ""
__licence__ = ""
__status__ = "TP minix fs"

from minix_inode import *
from bloc_device import *
import errno


class minix_file_system(object):
    """
        The main class of minix filesystem V1.0 API

        this class manage a minixfs :
            * alloc and free inode
            * reserve/free datablock in block bitmap
            * map relative entry in inode to absolute entry in filesystem
            * add data block to inode
            * check if a file exist in dinode
            * return inode number of an absolute path
            * add/remove entry in dir

        future usage :
            * test inode file type


    """
    def __init__(self, fs_src=None, port=None):
        """
            Constructor ; init the block to work with

            It could be a local file :
                minix = minix_file_system(filename)

            Or it could be a block server :
                minix = minix_file_system(server, port)


        :param fs_src: Could be file or a server (ip or hostname)
        :param port: in case of a connection to server, otherwise port=None
        """
        if fs_src and port:
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
        """
            Return the first free inode number available in inode bitmap
            starting at 0 up to (s.n_inodes)-1 ((nb of imap block*1024/16)*8).

            The bitmap ranges start at index 0 a finish at max_inod_num-1
            Inode 0 is never used even if it's set for python commodity. The
            inode 1 is the root of the filesystem.

        :return: the first free inode
        """
        try:
            pos = self.inode_map.index(False)
        except LookupError:
            raise MinixfsError("Error no more free inode in file system")

        self.inode_map[pos] = True
        self.inodes_list.pop(pos)  # clear
        self.inodes_list.insert(pos, minix_inode())  # insert new empty inode

        return int(pos)

    def ifree(self, inodnum):
        """
            Toggle an inode as available for the next ialloc()

        :param inodnum:  the inode to be freed
        :return: True if inodnum == False
        """

        # can't free root or inexistant inode
        if inodnum > self.disk.super_block.s_imap_blocks*BLOCK_SIZE*8 or inodnum < 2:
            raise MinixfsError("Error inode is out of bound")

        # inodes start at 1
        if self.inodes_list[inodnum]:
            self.inode_map[inodnum] = False

        return bool(~self.inode_map[inodnum])  # return 'not' state (true if false)

    def balloc(self):
        """
            Return the first free bloc index in the volume.

        :return: the first free bloc
        """
        try:
            pos = self.zone_map.index(False)
        except ValueError:
            raise MinixfsError("Error no space left on device")

        self.zone_map[pos] = True

        # data block start at 1
        return int(pos + self.disk.super_block.s_firstdatazone)

    def bfree(self, blocnum):
        """
            Toggle a bloc as available for the next balloc()

        :param blocnum: blocnum is an index in the zone_map
        :return: True if bloc is free
        """
        self.zone_map[blocnum] = False

        return ~self.zone_map[blocnum]

    def bmap(self, inode, blk):
        """
            Map a block number with his real block number on disk

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
            return int(struct.unpack_from('H', self.disk.read_bloc(inode.i_indir_zone), blk * 2)[0])

        blk -= MINIX_ZONESZ

        # double indirect blocks
        if blk < MINIX_ZONESZ ** 2:
            indir = blk / BLOCK_SIZE  # indirect bloc addr
            off = blk % MINIX_ZONESZ

            # read the second indirect block + read 'indirect' address and return 'offset' address
            return int(struct.unpack_from('H', self.disk.read_bloc(struct.unpack_from(
                'H', self.disk.read_bloc(inode.i_dbl_indr_zone), indir * 2)[0]), off * 2)[0])

        else:
            raise MinixfsError('Error Block is out of bound')

    def lookup_entry(self, dinode, name):
        """
            Lookup for a name in a directory, and return its inode number,
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
                inode = struct.unpack_from('H', content, off)[0]
                self.name = content[off + 2:off + DIRSIZE].split('\x00')[0]
                if inode != 0:
                    # add entry to dictionary
                    d_entry.update({self.name: inode})

            # pick next data block
            blk += 1
            data_block = self.bmap(dinode, blk)

        # return name in dict (raise error if not fund)
        try:
            return d_entry[name]
        except KeyError:
            return False

    def namei(self, path):
        """
            Take a path as input and return it's inode number

            Start from root and recursively look for subdir until
            last one fund and return the inode number of file
            (or dir)

        :param path: path to search
        :return: inode of the file
        """
        path = path[1:].split('/')
        self.inode = 1

        # if path empty it's root. So return inode = 1
        if not path[0]:
            return self.inode

        for i in path:
            try:
                self.inode = self.lookup_entry(self.inodes_list[self.inode], i)
            except:
                raise MinixfsError('Error file not found')

        return self.inode

    def ialloc_bloc(self, ino, blk):
        """
            Add a new data block at pos blk and return its real position on disk

        :param inode: the inode to add at
        :param blk: the block number to add (0,...,n-1)
        :return: the block address
        """
        inode = ino
        if blk < 7:
            if not inode.i_zone[blk]:
                inode.i_zone[blk] = self.balloc()
            return inode.i_zone[blk]

        if blk < MINIX_INODE_PER_BLOCK + 7:
            if not inode.i_indir_zone:
                inode.i_indir_zone = self.balloc()
                # write a new empty block to disk
                self.disk.write_bloc(bytearray("".ljust(1024, '\x00')), inode.i_indir_zone)
                log.debug("A new indirect block has been created")

            # if not already allowed write modified indirect block
            if not struct.unpack_from('H', self.disk.read_bloc(inode.i_indir_zone), blk-7):
                self.disk.write_bloc(2 + self.disk.super_block.s_imap_blocks,
                                     struct.pack_into('H', self.disk.read_bloc(inode.i_indir_zone, blk-7), blk-7,
                                                      self.balloc()))
            # now we can return it
            return struct.unpack_from('H', self.disk.read_bloc(inode.i_indir_zone), blk-7)

        if blk < (7 + MINIX_ZONESZ * (MINIX_ZONESZ+1)):
            # if double indirect block don't exist we need to add it in inode (and write it to disk)
            if not inode.i_dbl_indr_zone:
                inode.i_dbl_indr_zone = self.balloc()
                # write a new empty block to disk
                self.disk.write_bloc(inode.i_dbl_indr_zone, bytearray("".ljust(1024, '\x00')))
                log.debug("A new double indirect block has been created")

            # if this block is the first in the double indirect block we need to create an empty block for it
            if not struct.unpack_from('H', self.disk.read_bloc(inode.i_dbl_indr_zone), (blk-7-MINIX_ZONESZ)/MINIX_ZONESZ):
                new_blk = self.balloc()
                self.disk.write_bloc(inode.i_dbl_indr_zone, struct.pack_into('H',
                                self.disk.read_bloc(inode.i_dbl_indr_zone), (blk-7) % MINIX_ZONESZ, new_blk))
                # write a new empty block
                self.disk.write_bloc(bytearray("".ljust(1024, '\x00')), new_blk)

            # if not already allocated write modified second indirect block
            if not struct.unpack_from('H', self.disk.read_bloc(struct.unpack_from('H', self.disk.read_bloc(inode.i_dbl_indr_zone),
                                                      (blk-7-MINIX_ZONESZ) / MINIX_ZONESZ)), (blk-7) % MINIX_ZONESZ):

                struct.pack_into('H', self.disk.read_bloc(struct.unpack_from('H', inode.i_dbl_indr_zone,
                                          (blk-7-MINIX_ZONESZ) / MINIX_ZONESZ)), (blk-7) % MINIX_ZONESZ, self.balloc())

            # if block was previously allocated it's
            # now we return it - new one if a condition was
            return struct.unpack_from('H', struct.unpack_from('H', self.disk.read_bloc(inode.i_dbl_indr_zone),
                                                    (blk-7-MINIX_ZONESZ) / MINIX_ZONESZ), (blk-7) % MINIX_ZONESZ)

        else:
            raise MinixfsError('Error bmap: block is out of bound')

    def add_entry(self, dinode, name, new_node_num):
        """ add a new entry in a dinode (dir)

        :param dinode: inode number of the dir
        :param name: name of the file to be added
        :param new_node_num: inode of the new file
        """
        done = False
        blk = -1

        if len(name) > (DIRSIZE - 2):
            raise MinixfsError('Error add_entry: Filename too long')

        if self.lookup_entry(dinode, name):
            raise MinixfsError('Error add_entry: filename already exist in dir')

        if not self.is_dir(dinode):
            raise MinixfsError('Error add_entry: Could only add file in a dir')

        while not done:

            blk += 1
            data_block = self.bmap(dinode, blk)

            if data_block:
                self.content = bytearray(self.disk.read_bloc(data_block))

            elif blk < MINIX_ZONESZ ** 2 + MINIX_ZONESZ + 7:
                data_block = self.ialloc_bloc(dinode, blk)
                # empty new block
                self.content = bytearray("".ljust(1024, '\x00'))

            else:
                raise MinixfsError('Error add_entry: too many file in dir (fs overflow)')

            for off in xrange(0, BLOCK_SIZE, DIRSIZE):
                if not struct.unpack_from('H', self.content, off)[0]:
                    struct.pack_into('H', self.content, off, new_node_num)
                    self.content[off + 2:off + DIRSIZE] = name.ljust(DIRSIZE - 2, '\x00')
                    dinode.i_size += DIRSIZE
                    done = True
                    break

        if done:
            self.disk.write_bloc(data_block, self.content)
        else:
            raise MinixfsError('Error add_entry: Unable to add entry')

    def del_entry(self, dinode, name):
        """ delete filename from dir

        :param dinode: the directory's file
        :param name: filename to remove
        """
        blk = -1

        inode = self.lookup_entry(dinode, name)

        if not self.ifree(inode):
            raise MinixfsError('Error del_entry: Inode not freed')

        if not self.is_dir(dinode):
            raise MinixfsError('Error del_entry: This is not a dir')

        dir_block = 1

        # while dir block search inode
        while dir_block:
            blk += 1
            # try:
            dir_block = self.bmap(dinode, blk)
            # except:
            #     raise DelEntryError('Error deleting entry filename not found')

            # take a block
            dir_content = bytearray(self.disk.read_bloc(dir_block))

            # look for inode
            for i in xrange(0, BLOCK_SIZE, DIRSIZE):
                if inode == struct.unpack_from('H', dir_content, i)[0]:
                    # remove entry
                    # dir_content[i:i+DIRSIZE] = "".ljust(DIRSIZE, '\x00')
                    dir_content[i:i + 2] = "".ljust(2, '\x00')
                    self.bfree(dir_block)
                    if self.inodes_list[inode].i_nlinks > 1:
                        # inode has another name linked to it
                        self.inodes_list[inode].i_nlinks -= 1
                    else:
                        fb = 0
                        try:
                            file_blk = self.bmap(self.inodes_list[inode], fb)
                        except:
                            raise MinixfsError('Error deleting entry filename not found')

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
                self.bfree(dir_block)

        self.disk.write_bloc(dinode.i_zone[blk], dir_content)

    def is_dir(self, inode):
        """ Test if inode is a dir
        :param inode:
        :return: True if inode is a dir
        """
        return True if (inode.i_mode >> 12) == 4 else False

    def is_file(self, inode):
        """ Test if inode is a file
        :param inode:
        :return: True if inode is a file
        """
        return True if (self.inodes_list[inode].i_mode >> 12) == 8 else False

    def is_device(self, inode):
        """ Test if inode is a device
        :param inode:
        :return: True if inode is a device
        """
        return True if (self.inodes_list[inode].i_mode >> 12) == 2 else False

    def is_pipe(self, inode):
        """ Test if inode is a pipe
        :param inode:
        :return: True if inode is a pipe
        """
        return True if (self.inodes_list[inode].i_mode >> 12) == 1 else False

    def is_device_bloc(self, inode):
        """ Test if inode is a device bloc
        :param inode:
        :return: True if inode is a device block
        """
        return True if (self.inodes_list[inode].i_mode >> 12) == 6 else False

    def is_link(self, inode):
        """ Test if inode is a device link
        :param inode:
        :return: True if inode is a link
        """
        return True if (self.inodes_list[inode].i_mode >> 12) == 10 else False

    def update_bmap(self):
        """ Write bitarray map of data to disk
            cos we need a consistent filesystem
        :return: 0
        """
        offset = 2 + self.disk.super_block.s_imap_blocks
        # Write can only handle 1024 byte so need to slice (just in case)
        for i in range(self.disk.super_block.s_zmap_blocks):
            # write inode bitmap starting at bloc 2
            self.disk.write_bloc(offset + i,
                                 self.inode_map[i * (8 * BLOCK_SIZE):(i + 1) * (8 * BLOCK_SIZE) - 1].tobytes())

    def write_bloc_list(self):

        for i in range(self.disk.super_block.s_zmap_blocks):
            # start at bloc 2
            self.disk.write_bloc(2 + self.disk.super_block.s_imap_blocks + i,
                                 self.zone_map.tobytes()[i * BLOCK_SIZE:(i + 1) * BLOCK_SIZE])

    def __del__(self):
        """
            Destructor close connection with remote block server
        """
        del(self.disk)
        log.info('Close minix filesystem')


class MinixfsError(Exception):
    """ Class minixfs exceptions  """

    def __init__(self, message):
        super(MinixfsError, self).__init__(message)
        log.error(message)

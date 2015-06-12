# -*- coding: utf-8 -*-
"""
emulate a simple bloc device using a file
reading it only by bloc units
"""

__author__ = 'Sebastien Chassot'
__author_email__ = 'sebastien.chassot@etu.hesge.ch'

__version__ = "1.0.1"
__copyright__ = ""
__licence__ = ""
__status__ = "TP minix fs"


from minix_superbloc import *
from minix_exception import BlocDeviceException

import socket
import random as rand
import logging as log
# init the log

#LOG_FILENAME = 'minixfs_tester.log'

log.basicConfig(format='%(levelname)s:%(message)s', level=log.INFO)
#log.basicConfig(filename=LOG_FILENAME, level=log.DEBUG)


class bloc_device(object):
    """ Class block device
        This class open a minix filesystem created like this :

        $ truncate -s 10M new.minixfs.img
        $ mkfs.minix new.minixfs.img
            3424 inodes
            10240 blocks
            Firstdatazone=112 (112)
            Zonesize=1024
            Maxsize=268966912

        and performed read/write operation on it like a block device.

    """

    def __init__(self, blksize, pathname):
        """ Init a new block device """
        self.blksize = blksize

        # with open(pathname, 'br') as self.fd:
        try:
            self.fd = open(pathname, 'r+b')
        except:
            raise BlocDeviceException("Error unable to open file system")

        self.super_block = minix_superbloc(self)
        log.info("file system opened successfully")

    def __del__(self):
        """ Close properly the block device """
        new_sb = bytearray("".ljust(1024, '\x00'))
        clean_state = 1
        sb = struct.pack('HHHHHHIHH', self.super_block.s_ninodes, self.super_block.s_nzones,
                self.super_block.s_imap_blocks, self.super_block.s_zmap_blocks, self.super_block.s_firstdatazone,
                self.super_block.s_log_zone_size, self.super_block.s_max_size, self.super_block.s_magic, clean_state)
        new_sb[:sb.__len__()] = sb
        # self.write_bloc(MINIX_SUPER_BLOCK_NUM, new_sb)
        self.fd.close()
        log.info("file descriptor closed")

    def read_bloc(self, bloc_num, numofblk=1):
        """
            Read n block from block device and return
            the buffer

        :param bloc_num: block number to be read
        :param numofblk: number of block to be read
        :return: the buffer
        """
        try:
            self.fd.seek(bloc_num*self.blksize)
            buff = self.fd.read(int(numofblk*self.blksize))
        except:
            raise BlocDeviceException("Error read_bloc: Unable to read requested block")

        log.debug("Read block")

        return buff

    def write_bloc(self, bloc_num, bloc):
        """
            Write a block to block device
            the block must be equal to BLOCK_SIZE

        :param bloc_num: offset position of the block to be written
        :param bloc: buffer to be written
        :return: nb of bytes actually written
        """
        try:
            self.fd.seek(bloc_num*self.blksize)
            buff = self.fd.write(bloc)
        except:
            raise BlocDeviceException("Error Write_block: Unable to write requested block to disk")

        log.debug("Write block")

        return buff

class remote_bloc_device(object):
    """ Class remote block device

        This class connect to a remote bloc server and
        read/write commands are passed through a AF_INET
        socket.

        This connect to server running like this :

        $ truncate -s 10M new.minixfs.img
        $ mkfs.minix new.minixfs.img
            3424 inodes
            10240 blocks
            Firstdatazone=112 (112)
            Zonesize=1024
            Maxsize=268966912

        $ ./server {port} new.minixfs.img

        and send read/write request to it.

    """
    def __init__(self, blksize, host="localhost", port=1234):
        self.blksize = blksize
        self.requests = []
        self.responses = []
        self.fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.fd.connect((socket.gethostbyname(host), port))
        except:
            raise BlocDeviceException("Error remote_bloc_device: Couldnt connect to the block server")

        self.super_block = minix_superbloc(self)
        log.info("remote file system opened successfully")

    def __del__(self):
        """
            Cleanly close the socket when deleting object

        """
        self.close_connection()
        log.info('Closed bloc_device')

    def read_bloc(self, bloc_num, numofbloc=1):
        """
            Read n block from block device server

        :param bloc_num: the bloc number
        :param numofbloc: number of block to be read
        :return: the response
        """
        magic_req = int('76767676', 16)
        magic_resp = int('87878787', 16)
        rw_type = 0
        rand.seed(None)  # None = current system time
        handle = rand.randint(0, 2**32)
        offset = bloc_num*self.blksize
        length = numofbloc*self.blksize
        to_send = 0
        header_size = struct.calcsize('!IIIII')

        self.requests.insert(0, struct.pack('!IIIII', magic_req, rw_type, handle, offset, length))
        done = False
        buff = ""

        while not done:
            # send the header
            while to_send < header_size:
                sent = self.fd.send(self.requests[0][to_send:])
                if sent == 0:
                    raise BlocDeviceException("Error read_bloc: Lost connection with the server while sending request")
                to_send += sent

            log.debug("The request has been sent to the server")

            # read response
            response = ""
            response_size = struct.calcsize('!IiI')
            to_recv = 0

            while to_recv < response_size:
                b = self.fd.recv(response_size-to_recv)
                if b == '':
                    raise BlocDeviceException("Error read_bloc: socket connection broken while receiving response")

                response += b
                to_recv += len(b)

            log.debug("A response has been received")

            # TODO passer le code d'erreur en signed
            h = struct.unpack('!IiI', response)

            if h == (magic_resp, 0, handle):
            
                buff = ""
                to_recv = 0
                while to_recv < length:
                    b = self.fd.recv(length-to_recv)
                    if b == '':
                        raise BlocDeviceException("Error read_bloc: socket connection broken while receiving payload")
                    buff += b
                    to_recv += len(b)

                # remove request from fifo
                # self.requests.pop[0]
                done = True
                log.debug("A response has been received without any error")

            else:
                msg = "Error read_bloc: server return errno : "+h[1]
                raise BlocDeviceException(msg)

        return buff

    def write_bloc(self, bloc_num, bloc):
        """
            Write block from block device server
            the buffer must be equal to BLOCK_SIZE

        :param bloc_num: the bloc number
        :param bloc: buffer to be written
        """
        magic = int('76767676', 16)
        magic_resp = int('87878787', 16)
        rw_type = 1
        rand.seed(None)  # None = current system time
        handle = rand.randint(0, 2**32)
        offset = bloc_num*self.blksize

        # Can't write block not eq to BLOCK_SIZE it's a block server after all ?!
        if bloc.__len__() != self.blksize:
            raise BlocDeviceException("Error write_bloc: Block isn't equal to block size")

        to_send = 0
        header = struct.pack('!IIIII', magic, rw_type, handle, offset, self.blksize)
        self.requests.insert(0, header+bloc)

        while to_send < len(header+bloc):
            sent = self.fd.send(self.requests[0][to_send:])
            if sent == 0:
                raise BlocDeviceException("Error write_bloc: Lost connection while sending request")

            to_send += sent

        # read response
        responce = ''
        response_size = struct.calcsize('!IiI')
        to_recv = 0

        while to_recv < response_size:
            b = self.fd.recv(response_size-to_recv)
            if b == '':
                raise BlocDeviceException("Error read_bloc: socket connection broken while receiving response")
            responce += b
            to_recv += len(b)

        # Error treatment
        h = struct.unpack('!IiI', responce)

        if h[0] != magic_resp:
            raise BlocDeviceException('Error write_bloc: Server response unknown')

        if h[1] != 0:
            msg = "Error read_bloc: server return errno : "+h[1]
            raise BlocDeviceException(msg)

        if h[2] != handle:
            raise BlocDeviceException('Error write_bloc: Server send an unknown response handler')

    def close_connection(self):
        """ Close properly the filesystem

            the superblock shall be marked as clean and the socket
            closed.
        """
        # A new superblock
        new_sb = bytearray("".ljust(1024, '\x00'))
        clean_state = 1
        sb = struct.pack('HHHHHHIHH', self.super_block.s_ninodes, self.super_block.s_nzones,
                self.super_block.s_imap_blocks, self.super_block.s_zmap_blocks, self.super_block.s_firstdatazone,
                self.super_block.s_log_zone_size, self.super_block.s_max_size, self.super_block.s_magic, clean_state)
        # mark the superblock as clean
        new_sb[:sb.__len__()] = sb

        # close the socket
        try:
            self.fd.close()
            log.info("socket closed")
        except:
            raise BlocDeviceException("Error closing socket")

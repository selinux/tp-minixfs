# -*- coding: utf-8 -*-
# emulate a simple bloc device using a file
# reading it only by bloc units

__author__ = 'Sebastien Chassot'
__author_email__ = 'sebastien.chassot@etu.hesge.ch'

__version__ = "1.0.1"
__copyright__ = ""
__licence__ = ""
__status__ = "TP minix fs"

from constantes import *
from minix_superbloc import *
import socket
import random as rand
import errno
import logging as log

log.basicConfig(format='%(levelname)s:%(message)s', level=log.INFO)


class bloc_device(object):
    """ Class block device """

    def __init__(self, blksize, pathname):
        """ Init a new block device """
        self.blksize = blksize

        # with open(pathname, 'br') as self.fd:
        try:
            self.fd = open(pathname, 'r+b')
        except OSError:
            sys.exit("Error unable to open file system")

        self.super_block = minix_superbloc(self)
        log.info("file system opened successfully")

    def __del__(self):
        """ Close properly the block device """
        new_sb = bytearray("".ljust(1024, '\x00'))
        clean_state = 1
        sb = struct.pack('HHHHHHIHH', self.super_block.s_ninodes, self.super_block.s_nzones, self.super_block.s_imap_blocks, \
                    self.super_block.s_zmap_blocks, self.super_block.s_firstdatazone, self.super_block.s_log_zone_size,
                    self.super_block.s_max_size, self.super_block.s_magic, clean_state)
        new_sb[:sb.__len__()] = sb
        log.info("file system cleanly closed")
        # self.write_bloc(MINIX_SUPER_BLOCK_NUM, new_sb)
        self.fd.close()


    def read_bloc(self, bloc_num, numofblk=1):
        """ Read n block from block device
        :param bloc_num: block number to be read
        :param numofblk: number of block to be read
        :return: the buffer
        """
        # TODO test fs size and bloc_num comparison
        try:
            self.fd.seek(bloc_num*self.blksize)
            buff = self.fd.read(int(numofblk*self.blksize))
        except OSError, err:
            print(err)

        return buff

    def write_bloc(self, bloc_num, bloc):
        """ Write a block to block device
        :param bloc_num: block number to be written
        :param bloc: buffer to be written
        :return: nb of bytes actually written
        """
        try:
            self.fd.seek(bloc_num*self.blksize)
            n = self.fd.write(bloc)
        except OSError, err:
            print(err)

        return n

class remote_bloc_device(object):
    """ Class remote block device

        This class connect to a remote bloc server and
        read/write commands are passed through a
        TCP socket
    """

    def __init__(self, blksize, host="localhost", port=1234):
        self.blksize = blksize
        self.requests = []
        self.responses = []
        self.fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.fd.connect((socket.gethostbyname(host), port))
        except socket.error:
            print("Couldnt connect to the block server")
            sys.exit("Error unable to connect to block server")

        self.super_block = minix_superbloc(self)
        log.info("remote file system opened successfully")

    def __del__(self):
        """ Cleanly close the socket """
        new_sb = bytearray("".ljust(1024, '\x00'))
        clean_state = 1
        sb = struct.pack('HHHHHHIHH', self.super_block.s_ninodes, self.super_block.s_nzones, self.super_block.s_imap_blocks, \
                    self.super_block.s_zmap_blocks, self.super_block.s_firstdatazone, self.super_block.s_log_zone_size,
                    self.super_block.s_max_size, self.super_block.s_magic, clean_state)
        new_sb[:sb.__len__()] = sb
        self.close_connection()

    def read_bloc(self, bloc_num, numofbloc=1):
        """ Read n block from block device server

        :param bloc_num: the bloc number
        :param numofbloc: number of block to be read
        :return: the response
        """
        magic_req = int('76767676', 16)
        magic_resp = int('87878787', 16)
        rw_type = 0
        rand.seed(None) # None = current system time
        handle = rand.randint(0, 2**32)
        offset = bloc_num*self.blksize
        length = numofbloc*self.blksize
        to_send = 0
        header_size = struct.calcsize('!IIIII')

        #
        self.requests.insert(0, struct.pack('!IIIII', magic_req, rw_type, handle, offset, length))
        done = False
        buff = ""

        while not done:
            # send the header
            while to_send < header_size:
                sent = self.fd.send(self.requests[0][to_send:])
                if sent == 0:
                    raise RuntimeError("socket connection broken")
                to_send += sent

            # read response
            response = ""
            response_size = struct.calcsize('!III')
            to_recv = 0

            while to_recv < response_size:
                b = self.fd.recv(response_size-to_recv)
                if b == '':
                    raise RuntimeError("socket connection broken")

                response += b
                to_recv += len(b)

            h = struct.unpack('!III', response)

            if h == (magic_resp, 0, handle):
            
                buff = ""
                to_recv = 0
                while to_recv < length:
                    b = self.fd.recv(length-to_recv)
                    if b == '':
                        raise RuntimeError("socket connection broken")
                    buff += b
                    to_recv += len(b)

                # remove request from fifo
                # self.requests.pop[0]
                done = True

            else:
                raise RuntimeError("fail to read response")
                return h[1]

        return buff

    def write_bloc(self, bloc_num, bloc):
        """ Write block from block device server

        :param bloc_num: the bloc number
        :param bloc: buffer to be written
        """
        magic = int('76767676', 16)
        magic_resp = int('87878787', 16)
        rw_type = 1
        rand.seed(None) # None = current system time
        handle = rand.randint(0, 2**32)
        offset = bloc_num*self.blksize

        # Can't write block not eq to BLOCK_SIZE it's a block server after all ?!
        if bloc.__len__() != self.blksize:
            log.error("Block isn't equal to block size")
            raise BlockSizeError("Block isn't equal to block size")

        to_send = 0
        header = struct.pack('!IIIII', magic, rw_type, handle, offset, self.blksize)
        self.requests.insert(0, header+bloc)
        # TODO consolider while send
        while to_send < len(header+bloc):
            sent = self.fd.send(self.requests[0][to_send:])
            if sent == 0:
                raise RuntimeError("socket connection broken")
            to_send += sent

        # read response
        responce = ''
        response_size = struct.calcsize('!III')
        to_recv = 0

        while to_recv < response_size:
             b = self.fd.recv(response_size-to_recv)
             if b == '':
                 raise RuntimeError("socket connection broken")
             responce += b
             to_recv += len(b)

        h = struct.unpack('!III', responce)
        # TODO resend, close and pop
        # self.requests.pop[0]

    def close_connection(self):
        """ close properly the socket """

        try:
            self.fd.close()
            log.info("socket cleanly closed")
        except:
            log.error("Error closing socket")


class MyBaseException(Exception):
    """ Class minixfs exceptions  """
    def __init__(self, message):
        super(MyBaseException, self).__init__(message)
        self.message = message

class BlockSizeError(MyBaseException):
    pass

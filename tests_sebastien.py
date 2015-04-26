#! /usr/bin/python3
# -*- coding: utf-8 -*-

#
# Description : Test unitaire opur le miniprojet Minifs
#

__author__ = 'Sebastien Chassot'
__author_email__ = 'sebastien.chassot@etu.hesge.ch'

__version__ = "1.0.1"
__copyright__ = ""
__licence__ = "GPL"
__status__ = "Exercices"



import unittest
from minixfs import *
import os

testfile="minixfs_lab1.img"
workfile=testfile+".gen"
workfilewrite=testfile+".genwrite"
string="dd if="+testfile+" of="+workfile+" bs=1024 2>/dev/null"
os.system(string)

class TestStringMethods(unittest.TestCase):

    def test_bmap(self):
        self.maxDiff = None
        minixfs=minix_file_system(workfile)
        # for i in range(7, 519):
        #     print(minixfs.bmap(minixfs.inodes_list[167], i).__str__())
        for i in range(520, 529):
            print(minixfs.bmap(minixfs.inodes_list[167], i).__str__())

    # def test_upper(self):
    #     self.assertEqual('foo'.upper(), 'FOO')
    #
    # def test_isupper(self):
    #     self.assertTrue('FOO'.isupper())
    #     self.assertFalse('Foo'.isupper())
    #
    # def test_split(self):
    #     s = 'hello world'
    #     self.assertEqual(s.split(), ['hello', 'world'])
    #     # check that s.split fails when the separator is not a string
    #     with self.assertRaises(TypeError):
    #         s.split(2)

if __name__ == '__main__':
    unittest.main()


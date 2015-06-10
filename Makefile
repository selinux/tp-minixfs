CFLAGS=-g -Wall -std=c99 
CC=gcc
SRC= server.c server.h
FILESYSTEM=./filesystems
ORG=$(FILESYSTEM)/minixfs_lab1.img.org
NEW=$(FILESYSTEM)/remote_minixfs_lab1.img
port=1234

all : server

server: $(SRC)
	$(CC) $(CFLAGS) $? -o $@

run: server
	cp $(ORG) $(NEW)
	./server $(port) $(NEW)

run_debug: server
	cp $(ORG) $(NEW)
	strace ./server $(port) $(NEW)

run_doc: 
	pydoc -b


# Efface fichiers objets et exécutable
clean:
	rm server
	rm $(NEW)


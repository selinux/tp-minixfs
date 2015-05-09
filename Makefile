CFLAGS=-g -Wall -std=c99 
CC=gcc
FILES= server.c server.h

all : $(TP03)

server: $(FILES)
	$(CC) $(CFLAGS) $? -o $@

# Efface fichiers objets et exécutable
clean:
	rm server

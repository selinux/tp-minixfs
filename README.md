# Mini-projet de programmation Système/Systèmes d’exploitation 

## Utilisation 


```
# build the c server

    $ make server

# run self test

    $ make test1          # or test2

# run server (befor client)

    $ make run            # or run_debug
    $ make test_server    # in other terminal

# see doc in browser

    $ make doc

```


## Une image Minix-FS version 1.0 accessible localement et à distance 

MINIX-FS est un système de fichier créé par Andrew Tanenbaum en 1987, il se base sur le système
de fichiers UNIX dont les aspects complexes ont été retirés pour garder une structure simple et
didactique. L'objectif de ce projet est d'implémenter un système de fichier MINIX accessible en
lecture et en écriture depuis un fichier image formaté en au format MINIX version 1.

En raison de la définition du superbloc, MINIX version 1 est limité à une image divisée en un
maximum de 65535 blocs et ne pourra contenir qu'un maximum de 65535 inodes. C'est peu mais
amplement suffisant pour mettre en pratique les principes généraux de conception d'un système de
fichier.

L'accès local au fichier image contenant le système de fichier MINIX devra être implémenté en
python en utilisant les primitives d'accès aux fichiers classiques. L'accès distant devra être
implémenté via des sockets python pour la partie cliente. Le client se connectant à un serveur de
bloc implémenté en langage C.

La manipulation locale des structures de données stockées sur l'image récupérée via une lecture de
blocs locale ou à distante se fera exclusivement en langage python version 2, par l'intermédiaire du
canevas des classes python fournis avec le projet.

Pour simplifier les traitements, l'entièreté de la table des inodes du système de fichier sera chargée
en mémoire dans une liste, donc l'index 0 ne contiendra qu'un inode vide. Dans un système de
fichier réel, seul un sous-ensemble des inodes sont en mémoire à un instant donné.


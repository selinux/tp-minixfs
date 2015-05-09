/*
 * =====================================================================================
 *
 *       Filename:  server_de_blocks.c
 *
 *    Description:  Le but de l'exercice suivant est d'écrire un mini-serveur de blocs
 *                  en C issu d'un même fichier donné en paramètre. Le serveur  devra
 *                  implémenter un simple protocole requête-réponse qui respecte le
 *                  format requêtes/réponse suivants, transporté sur TCP/IP via des sockets
 *                  C AF_INET de type SOCK_STREAM. L'ensemble des données est représenté
 *                  en big endian, c'est à dire l'ordre conventionnel pour l'ensemble des
 *                  protocole réseaux TCP/IP :
 *                      les bits de poids fort sont en premier.
 *
 *        Version:  1.0
 *        Created:  Monday 09 March 2015 07:47:11  CET
 *       Revision:  none
 *       Compiler:  gcc
 *
 *         Author:  Sebastien Chassot (sinux), sebastien.chassot@etu.hesge.ch
 *        Company:  HES-SO hepia section ITI (soir)
 *
 * =====================================================================================
 */

#define _GNU_SOURCE

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netinet/ip.h>
#include <arpa/inet.h>
#include <stdbool.h>
#include <inttypes.h>
#include <netdb.h>

#include "server.h"


int main(int argc, char* argv[])
{

    int s, fd;                         /* the socket and file fd */
    int clients;                       /* client socket list */
    struct sockaddr_in addr_internet, addr_client;
    int s_len = sizeof(addr_client);   /* pointer to size of the struct sockaddr_in */

    /* menu */
    if(argc<2)
    {
        printf("Usage : %s <port> <file>\n", argv[0]);
        return(EXIT_FAILURE);
    }

    /* Open the file from we'll read/write with */
    if((fd=open(argv[2], O_CREAT | O_RDWR, S_IRUSR|S_IWUSR|S_IRGRP|S_IWGRP)) < 0)
        perror("Error opening file");

    /* create the socket */
    addr_internet.sin_family = AF_INET;
    addr_internet.sin_addr.s_addr = INADDR_ANY;   /* use my IP adresse */
    addr_internet.sin_port = (in_port_t) htons(atoi(argv[1]));
    bzero(&(addr_internet.sin_zero), 8);    /* zero the struct */


    if((s=socket(AF_INET, SOCK_STREAM, 0))<0)
        ERR_FATALE("Error creating socket");

    if(bind(s, (struct sockaddr *)&addr_internet, sizeof(addr_internet))<0)
        ERR_FATALE("Error binding socket");

    if(listen(s, MAX_CONNEXIONS) < 0)
        perror("Unable to set listner");

    /* socket initialisation finished */

    if((clients=accept(s, (struct sockaddr *)&addr_client, (socklen_t *)&s_len))<0)
        ERR_FATALE("Error accepting client");

    /* Start the job */

    char buff[BUFF_SIZE];
    char magic[5];
    sprintf(magic, "%s", "vvvv");
    char *str_pos = buff;
    uint32_t len = 0;


    while(1)
    {
        ssize_t nread;
        bool is_magic = false;

        /* fill buffer */
        while(len < BUFF_MIN_SIZE)
        {
            nread = read(clients, str_pos, BUFF_MIN_SIZE-len);
            if (nread < 0)
                ERR_FATALE("Error reading socket");

            str_pos += nread;
            *str_pos = '\0';
            len += nread;
        }

        /* header check */
        char *header_start = strstr(buff, magic);
        int tr = buff-header_start;

        if(header_start && len-tr < HEADER_SIZE*sizeof(uint32_t))
        {
            str_pos = header_start;
            translate_string(buff, header_start, len);
            perror("Part of request lost, magic not fund");

            len -= tr;
        }
        else if (header_start)
            is_magic = true;

        struct query_header_st query;
        if(is_magic) {

            char tmp[33];
            strncpy(tmp,buff,32);
            char *test = (char *)&query;

            /* transfer the buffer data to the query structure */
            for(int i = 0;i < HEADER_SIZE*sizeof(uint32_t); i++)
                *(test+i) = buff[i];

//            char tst[] = "ksfjhjkdh jkhdfjak jkldfh kljsdafh kjdfsajk dfklsjhdf skj";
//            printf("%s\n", tst);
//            translate_string(tst, *(&tst+10), 10);
//            printf("%s\n", tst);

            query.sign = ntohl(query.sign);
            query.type = ntohl(query.type);
            query.handle = ntohl(query.handle);
            query.offset = ntohl(query.offset);
            query.length = ntohl(query.length);
            struct hostent * h;
            if((h=gethostbyname("t440p"))<0)
                perror("gethostname prob");
            else
                printf("host = %s\n", h->h_name);
            printf("magic : %x\n", query.sign);
            printf("type : %x\n", query.type);
            printf("handle : %x\n", query.handle);
            printf("offset : %x\n", query.offset);
            printf("lenght : %x\n", query.length);
        }

        struct response_header_st resp;
        resp.sign = htonl(0x87878787);
        resp.handle = htonl(query.handle);
        resp.length = query.length;
        resp.ernum = 0;

        if(query.type!=1)  /* a read is less risky than a write */
        {
            if((resp.ernum = lseek(fd, query.offset, SEEK_SET))<0)
            {
                resp.ernum = htonl(resp.ernum);
                write(s,(char *)&resp, sizeof(struct response_header_st));
            }
            else if((resp.ernum = read(fd, buff, query.length))<0)
            {
                resp.ernum = htonl(resp.ernum);
                write(clients,(char *)&resp, sizeof(struct response_header_st));
            }
            else
            {
                resp.ernum = htonl(resp.ernum);
                write(clients,(char *)&resp, sizeof(struct response_header_st));
                write(clients,buff, query.length);
            }
        }
        else
        {
            struct query_st to_client;

            to_client.head = &resp;

            uint8_t * pay[resp.length];
            nread = 0;
            int tread = resp.length;

            nread=read(clients,&pay, tread);

            do
            {
                nread = read(clients, pay[resp.length-tread], tread);
                if(nread < 0)
                    ERR_FATALE("Error read payload from client");

            }while(tread > 0);

            if((to_client.head->ernum=lseek(fd, query.offset, SEEK_SET))<0)
                ERR_FATALE("Error writing offset");

            if((to_client.head->ernum=write(fd,pay,query.length))<0)
                    ERR_FATALE("Error writing payload to fd");

            if((nread=write(clients, (char *) &resp, sizeof(struct response_header_st)))<0)
                ERR_FATALE("Error responding client");
        }
    }

    printf("\nJob done !!!\n\n");

    if(close(s)<0)
        perror("Error closing socket fd");

    return EXIT_SUCCESS;
}

/**
* @brief translate a string back to the begining of a buffer
*
* @parm the bbuffer to be corrected
* @parm the string position in the buffer
* @parm
* @return alvays 0 (unused)
*/
int translate_string(char *str, char *position, int length)
{
    int i = 0;

    printf("l'offset est de %d et len = %d\n", (int)(str-position), length);
    while(i < length)
        *(str+i)=*(position+i++);    /* translate char */

    return 0;
}


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


#include "server.h"

#define DEBUG

int main(int argc, char* argv[])
{

    int s, fd;                         /* the socket and file fd */
    int client;                       /* client socket list */
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


    if( (s=socket(AF_INET, SOCK_STREAM, 0)) < 0)
        ERR_FATALE("Error creating socket");

    if( bind(s, (struct sockaddr *)&addr_internet, sizeof(addr_internet)) < 0)
        ERR_FATALE("Error binding socket");

    if( listen(s, MAX_CONNEXIONS) < 0)
        perror("Unable to set listner");

    /* socket initialisation finished */

    bool exit_prog = false;

    do {
        if ((client = accept(s, (struct sockaddr *) &addr_client, (socklen_t *) &s_len)) < 0)
            ERR_FATALE("Error accepting client");

        /* Start the job */

        while ( client ) {

            query_header_t * header = calloc(sizeof(query_header_t), 1);
            response_header_t response;

            if (read_header(client, &header) < 0) {
                perror("Unable to read header request");
                continue;
            }

            response.sign = htonl(SIGN_RESPONSE);
            response.errnum = 0x0;
            response.handle = htonl(header->handle);

            char * buff;

            if (header->type == 0x0) {

                if( read_request(fd, &buff, header->offset, header->length) < 0 )
                {
                    perror("Error unable to read request ");
                    response.errnum = errno;
                }

                if( write(client, (char *)&response, sizeof(response_header_t)) < 0 )
                    ERR_FATALE("Error lost client connexion")

                if( write(client, buff, header->length) < 0 )
                    ERR_FATALE("Error lost client connexion")

                #ifdef DEBUG
                write(1, (char *)&response, sizeof(response_header_t));
                write(1, &buff, header->length);
                #endif

            } else {

                if (header->type != 0x1) {
                    perror("Error unknown client request type");
                    response.errnum = EBADE; // invalide exchange
                }

                if( read_payload(client, &buff, header->length) < 0){
                    perror("Error reading payload");
                    response.errnum = errno;
                }

                if( write_payload(fd, &buff, header->offset, header->length) < 0)
                {
                    perror("Error lseek failure");
                    response.errnum = errno;
                }

                if( write(client, (char *)&response, sizeof(response_header_t)) < 0 )
                    ERR_FATALE("Error lost client connexion")

                #ifdef DEBUG
                write(1, (char *)&response, sizeof(response_header_t));
                #endif
            }

            free(buff);
            free(header);
        }

    } while( !exit_prog );

    printf("\nJob done !!!\n\n");

    if(close(s)<0)
        perror("Error closing socket fd");

    return EXIT_SUCCESS;
}

/**
* @brief translate a string back to the begining of a buffer
*
* @parm the buffer to be corrected
* @parm the string position in the buffer
* @parm
* @return always 0 (unused)
*/
int translate_string(char **buff, int offset)
{
    int i = 0;
    int length = strlen(*buff);

    while(i < length-offset) {
        *(buff + i) = *(buff + offset + i);    /* translate char */
        i++;
    }

    return 0;
}

/**
 *  @brief read the header of a socket socket
 *
 *  @parm header: pointer to header who'll be modified
 *  @parm socket: the socket to be read
 *  @return: success 0  -1 in case of failure
 */
int read_header(int socket, query_header_t ** header)
{

    int header_length = sizeof(query_header_t);
    char buff[header_length];
    char * begin;
    query_header_t * tmp_header;

    int n = 0, offset = 0;

    do{

        n += read(socket, buff, header_length - n);
        begin = strstr(buff, "vvvv");
        if (begin)
        {
            // distance between pointers
            offset = begin-buff;
//            translate_string(&buff, offset);
//            strncpy(buff, begin, n);
            n -= offset;
        }

    } while ( n < header_length );

    tmp_header = (query_header_t *)buff;

    (*header)->sign = ntohl(tmp_header->sign);
    (*header)->type = ntohl(tmp_header->type);
    (*header)->handle = ntohl(tmp_header->handle);
    (*header)->offset = ntohl(tmp_header->offset);
    (*header)->length = ntohl(tmp_header->length);

    return 0;
}


int read_request(int fd, char ** buff, uint32_t offset, uint32_t length)
{

    char *b = calloc(sizeof(char), length);
    uint32_t n = 0;

    if( lseek(fd, offset, SEEK_SET) < 0)
    {
        perror("Error lseek failure");
        return -1;
    }

    do {

        n += read(fd, b, length-n);
        if(n < 0)
        {
            perror("Error unable to read file");
            free(b);
            return -1;
        }

    }while( n < length);

    *buff = b;

    return 0;
}


int read_payload(int socket, char ** buff, uint32_t length)
{
    char *b = calloc(sizeof(char), length);
    uint32_t n = 0;

    do {
        n += read(socket, b, length-n);
        if(n < 0)
        {
            perror("Unable to read payload");
            free(b);
            return -1;
        }

    } while (n < length);

    *buff = b;

    return 0;
}


int write_payload(int fd, void* buff, uint32_t offset, uint32_t length)
{

    if( lseek(fd, offset, SEEK_SET) < 0 )
    {
        perror("Error lseek failure");
        return -1;
    }

    if( write(fd, buff, length) < 0)
    {
        perror("Error unable to write payload to file");
        return -1;
    }

    return 0;
}

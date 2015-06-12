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

        client = accept(s, (struct sockaddr *) &addr_client, (socklen_t *)&s_len);

        if(write(1, "Client connected\n", 17) < 0)
            ERR_FATALE("Error writing stdout");

        if (client < 0)
            ERR_FATALE("Error accepting client");

        /* finish client session, back to accept next one */
        bool end_session = false;

        /* Start the job */
        do {

            /* prepare a new request */
            query_header_t * header = calloc(sizeof(query_header_t), 1);
            response_header_t response;

            /*************************************
             * read a new request
             *************************************/
            int n = read_header(client, &header);

            if ( n < 0)
            ERR_FATALE("Unable to read header request");

            /* lost client connection so break for a new one */
            if ( n == 0 ){
                perror("Client disconnected end session");
                free(header);
                end_session = true;
                break;
            }

            /* prepare the response */
            response.sign = htonl(SIGN_RESPONSE);
            response.errnum = 0x0;
            response.handle = htonl(header->handle);

            /* need a buffer for the response we use the same for
               client's payload or file system response */
            void * buff = calloc(sizeof(char), header->length);

            switch (header->type) {

                case 0 :  /* read case */

                    /*******************************
                     * read request on disk
                     *******************************/
                    n = read_response_on_fs(fd, &buff, header->offset, header->length);
                    if ( n < 0) {
                        perror("Error unable to read file system");
                        response.errnum = errno;
                        free(buff);
                        buff = NULL;
                    }

                    /********************************
                     * send response header
                     *******************************/
                    n = write_to_client(client, (char *) &response, sizeof(response_header_t));

                    if( n <= 0 ) {
                        perror("Error lost client connection");
                        free(header);
                        free(buff);
                        close(client);
                        end_session = true;
                        break;
                    }
#ifdef DEBUG
    printf("Write to client (header) :\n\n");
    printf("Signature = %x\n",response.sign);
    printf("Error     = %d\n",response.errnum);
    printf("Handel    = %x\n",response.handle);
    printf("\n=================================\n\n");
#endif
                    /*******************************
                     * send response if any
                     *******************************/
                    if (buff) {
                        n = write_to_client(client, (char *) buff, header->length);

                        if( n <= 0 ) {
                            perror("Error lost client connection");
                            free(buff);
                            close(client);
                            end_session = true;
                            break;
                        }
                        free(buff);
                    }

                    free(header);
                    break;

                case 1 :  /* write case */

                    /*****************************
                     * read the payload
                     *****************************/
                    n = read_client_payload(client, &buff, header->length);
                    if ( n < 0) {
                        perror("Error reading payload");
                        response.errnum = errno;
                        free(buff);
                        buff = NULL;
                    }

                    if ( n == 0) {
                        perror("Error lost client connection");
                        free(header);
                        close(client);
                        end_session = true;
                        break;

                    } else {

                        /*****************************
                         * write payload to disk
                         *****************************/
                        if (write_to_disk(fd, (char *)buff, header->offset, header->length) < 0) {
                            perror("Error unable to write payload to disk");
                            response.errnum = errno;
                        }
                    }

                    /****************************
                     * send response to client
                     ****************************/
                    n = write_to_client(client, (char *) &response, sizeof(response_header_t));
#ifdef DEBUG
    printf("Write to client (header) :\n\n");
    printf("Signature = %x\n",response.sign);
    printf("Error     = %d\n",response.errnum);
    printf("Handel    = %x\n",response.handle);
    printf("\n=================================\n\n");
#endif
                    if( n <= 0 ) {
                        perror("Error lost client connection while responding");
                        free(header);
                        close(client);
                        end_session = true;
                        break;
                    }

                    free(header);
                    free(buff);
                    break;

                default :
                    perror("Error unknown client request type");
                    response.errnum = EBADE; // invalide exchange
                    n = write_to_client(client, (char *) &response, sizeof(response_header_t));

                    if( n <= 0 ) {
                        perror("Error lost client connection while responding");
                        free(header);
                        close(client);
                        end_session = true;
                        break;
                    }


            }

        } while ( !end_session);

    } while( !exit_prog );

    printf("\nJob done !!!\n\n");

    if(close(s)<0)
        perror("Error closing socket fd");

    return EXIT_SUCCESS;
}


/**
 *  @brief read the header of a request
 *
 *  @parm socket: the socket to be read
 *  @parm header: pointer to header who'll be modified
 *
 *  @return: number of byte read, -1 in case of failure
 */
int read_header(int socket, query_header_t ** header)
{

    int header_length = sizeof(query_header_t);

    /* temporary buffer to stock header and possible garbage */
    char buff[1000];

    /* convert the magic */
    char magic[5];

    uint32_t * uint_magic_p = (uint32_t *)magic;
    *uint_magic_p = SIGN_REQUEST;  /* write the magic in magic buffer */
    /* could have been remplaced by  sprintf(magic,"%x", SIGN_RESPONSE); */

    char * begin;
    query_header_t * tmp_header;

    int n = 0, r = 0, offset = 0;

    do{

        n = read(socket, buff, header_length - r);
        r += n;
        if( n <= 0 )
            return n;

        begin = strstr(buff, magic);

        if (begin)
        {
            /* distance between pointers */
            offset = begin-buff;
            r -= offset;
        }

    } while ( n < header_length );

    tmp_header = (query_header_t *)buff;

    (*header)->sign = ntohl(tmp_header->sign);
    (*header)->type = ntohl(tmp_header->type);
    (*header)->handle = ntohl(tmp_header->handle);
    (*header)->offset = ntohl(tmp_header->offset);
    (*header)->length = ntohl(tmp_header->length);

#ifdef DEBUG
    system("clear");
    printf("Read from client (header) :\n\n");
    printf("Signature = %x\n",tmp_header->sign);
    printf("Handel    = %x\n",tmp_header->handle);
    printf("Offset    = %d\n",tmp_header->offset);
    printf("Lenght    = %d\n",tmp_header->length);
    printf("\n=================================\n\n");
#endif

    return r;
}

/**
 * @brief read the requested block on fs
 *
 * @parm fd: the file descriptor
 * @parm buff: buffer for the answer (memory need to be allocated)
 * @parm offset: the position in file
 * @parm the length to be read
 *
 * @return: return a non-negative integer indicating the number of bytes actually read.
 *          or 0 if lost connection or negative integer in case of error
 */
int read_response_on_fs(int fd, void **buff, uint32_t offset, uint32_t length)
{

    int n = 0, r = 0;

    n = lseek(fd, offset, SEEK_SET) < 0;
    if( n < 0) {
        perror("Error lseek failure");
        return n;
    }

    do {

        n = read(fd, *buff, length - r);
        r += n;
        buff += n;

        if(n <= 0) {
            perror("Error unable to read file");
            return n;
        }

    }while( r < length);

//#ifdef DEBUG
//    printf("\nRead \t %d bytes on disk at pos %d\n", r, offset);
//#endif

    return r;
}

/**
 * @brief read the client payload
 *
 * @parm socket: the socket
 * @parm buff: buffer for the payload (memory need to be allocated)
 * @parm the length to be read
 *
 * @return: return a non-negative integer indicating the number of bytes actually read.
 *          or 0 if lost connection or negative integer in case of error
 */
int read_client_payload(int socket, void **buff, uint32_t length)
{
    int n = 0, r = 0;

    do {
        n = read(socket, *buff, length-n);
        r += n;
        buff += n;

        if(n <= 0)
        {
            perror("Unable to read payload");
            return n;
        }

    } while (r < length);

//#ifdef DEBUG
//    printf("\nRead \t %d more bytes from client\n", r);
//#endif

    return r;
}

/**
 * @brief write the payload datas to fs
 *
 * @parm fd: the file descriptor (file system)
 * @parm buff: data to be written
 * @parm offset: the position in file system
 * @parm the length to be written
 *
 * @return: return a non-negative integer indicating the number of bytes actually read.
 *          or 0 if lost connection or negative integer in case of error
 */
int write_to_disk(int fd, void *buff, uint32_t offset, uint32_t length)
{
    int n, r = 0;

    n = lseek(fd, offset, SEEK_SET);
    if( n < 0 ) {
        perror("Error lseek failure");
        return n;
    }

    do {

        n = write(fd, (char*)buff, length - r);
        r += n;

        buff += n;

        if( n < 0 ) {
            perror("Error writing payload to disk");
            return n;
        }

    }while( r < length);

//#ifdef DEBUG
//    printf("\nWrote \t %d bytes to disk (bloc %d)\n", r, offset/1024);
//#endif

    return r;
}
/**
 * @brief send the payload back to client
 *
 * @parm fd: the socket
 * @parm buff: data to be sent
 * @parm the length to be written
 *
 * @return: return a non-negative integer indicating the number of bytes actually read.
 *          or 0 if lost connection or negative integer in case of error
 */
int write_to_client(int sock, void *buff, uint32_t length)
{
    int n, r = 0;

    do {

        n = write(sock, (char*)buff, length - r);
        r += n;
        buff += n;

        if( n < 0 ) {
            perror("Error sending payload to client");
            return n;
        }

    }while( r < length);

    return r;
}

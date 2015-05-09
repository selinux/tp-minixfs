/* =====================================================================================
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
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netinet/ip.h>
#include <arpa/inet.h>

#define MAX_CONNEXIONS 1
#define BUFF_SIZE 70000
#define BUFF_MIN_SIZE 20
#define HEADER_SIZE 5
#define SIGN_REQUEST 0x76767676
#define SIGN_RESPONSE 0x87878787
#define CMD_READ 0x0
#define CMD_WRITE 0x1


#define ERR_FATALE(msg) {\
    perror((msg)); exit(EXIT_FAILURE);}


struct __attribute__((packed)) query_header_st
{
    uint32_t sign;      // message signature
    uint32_t type;      // type (read = 0x0 / write= 0x1)
    uint32_t handle;    // message handle
    uint32_t offset;    // start offset
    uint32_t length;    // length reading
};

struct __attribute__((packed)) response_header_st
{
    uint32_t sign;      // message signature
    uint32_t ernum;     // return value
    uint32_t handle;    // message handle
    uint32_t length;    // payload length
};

struct __attribute__((packed)) query_st
{
    struct response_header_st  *head;      // header
    uint8_t *payload;   // attached payload
};


struct __attribute__((packed)) request_st
{
    struct query_header_st  *head;      // header
    uint8_t *payload;   // attached payload
};


int translate_string(char *str, char *pos, int len);

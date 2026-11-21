#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "translate.h"
extern int translate_set_readonly_dir(const char *) __attribute__((weak));
int main(int argc, char **argv) {
 char data[64]={0}; int fd,flags;
 if (!translate_set_readonly_dir) {fprintf(stderr,"explicit read-only mode missing\n");return 99;}
 if(argc!=4)return 98;
 if(translate_set_readonly_dir(argv[1])<0){perror("configure");return 2;}
 flags=atoi(argv[3]);errno=0;fd=translate_open(argv[2],flags);
 if(fd<0){printf("rejected errno=%d\n",errno);return 3;}
 if((fcntl(fd,F_GETFL)&O_ACCMODE)!=O_RDONLY)return 97;
 if(read(fd,data,sizeof(data)-1)<0)return 96;
 close(fd);printf("read=%s\n",data);return 0;
}

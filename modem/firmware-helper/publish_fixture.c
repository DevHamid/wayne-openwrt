/* Source-derived vendor forwarding-gate model; no real sockets. */
#include <assert.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <sys/socket.h>
#include <linux/qrtr.h>
#include <libqrtr.h>
#include "ns.h"
static unsigned local_node=1,remote_zero=1,delivered,dropped;
static struct qrtr_ctrl_pkt observed;
int __wrap_getsockname(int fd,struct sockaddr *addr,socklen_t *length){
 struct sockaddr_qrtr local={.sq_family=AF_QIPCRTR,.sq_node=local_node,.sq_port=16480};
 assert(fd==100);assert(*length>=sizeof(local));memcpy(addr,&local,sizeof(local));*length=sizeof(local);return 0;
}
ssize_t __wrap_sendto(int fd,const void *data,size_t length,int flags,const struct sockaddr *addr,socklen_t addrlen){
 const struct sockaddr_qrtr *destination=(const void *)addr;
 assert(fd==100 && length==sizeof(observed));assert(addrlen==sizeof(*destination));
 assert(destination->sq_node==local_node && destination->sq_port==QRTR_PORT_CTRL);
 memcpy(&observed,data,length);
 assert(le32_to_cpu(observed.cmd)==QRTR_TYPE_NEW_SERVER);
 assert(le32_to_cpu(observed.server.service)==4096 && le32_to_cpu(observed.server.instance)==1);
 /* qrtr_sendmsg looks up pkt.server.node before qrtr_must_forward(src,NULL). */
 if(remote_zero && le32_to_cpu(observed.server.node)==0){dropped++;return 0;}
 delivered++;return (ssize_t)length;
}
int main(int argc,char **argv){
 if(argc>1 && !strcmp(argv[1],"no-remote"))remote_zero=0;
 if(argc>1 && !strcmp(argv[1],"node9"))local_node=9;
 int result=qrtr_publish(100,4096,1,0);
 printf("result=%d delivered=%u dropped=%u advertised_node=%u advertised_port=%u\n",result,delivered,dropped,le32_to_cpu(observed.server.node),le32_to_cpu(observed.server.port));
 return result==0 && delivered==1 && dropped==0?0:1;
}

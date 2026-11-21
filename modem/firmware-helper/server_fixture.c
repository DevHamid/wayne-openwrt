#define _GNU_SOURCE
#define main upstream_main
#include "source/tqftpserv.c"
#undef main
#include <assert.h>
#include "ns.h"
static unsigned socket_calls, data_sends, error_code, received;
static int nextfd=100;
static int bulk_mode;
static size_t bulk_received;
static unsigned last_block,large_allocations;
static unsigned published,closed_sockets;
static unsigned publication_keys[10],publication_ports[10],closed_seen[1024];
static const char *rx_case;
static int fail_publish,fail_socket,fail_select,high_socket,select_last,last_listener;
extern void *__real_calloc(size_t,size_t);
void *__wrap_calloc(size_t n,size_t size){if(size && n>1048576/size){large_allocations++;return NULL;}return __real_calloc(n,size);}
int __wrap_socket(int domain,int type,int protocol){assert(domain==AF_QIPCRTR);socket_calls++;if(fail_socket && socket_calls==4){errno=EMFILE;return -1;}if(high_socket)return FD_SETSIZE;return nextfd++;}
int __wrap_bind(int fd,const struct sockaddr *addr,socklen_t len){return 0;}
int __wrap_connect(int fd,const struct sockaddr *addr,socklen_t len){return 0;}
int __wrap_setsockopt(int fd,int level,int opt,const void *v,socklen_t len){return 0;}
int __wrap_getsockname(int fd,struct sockaddr *addr,socklen_t *len){struct sockaddr_qrtr q={.sq_family=AF_QIPCRTR,.sq_node=1,.sq_port=16480+(unsigned)(fd-100)};memcpy(addr,&q,sizeof(q));*len=sizeof(q);return 0;}
extern int __real_close(int fd);
int __wrap_close(int fd){if(fd>=100){assert(fd<1124 && !closed_seen[fd-100]++);closed_sockets++;return 0;}return __real_close(fd);}
ssize_t __wrap_send(int fd,const void *data,size_t len,int flags){const unsigned char *p=data;assert(len>=4);unsigned op=(p[0]<<8)|p[1];if(op==OP_DATA){data_sends++;if(bulk_mode){unsigned b=(p[2]<<8)|p[3];assert(b==last_block+1);last_block=b;for(size_t i=4;i<len;i++)assert(p[i]==(bulk_received+i-4)%251);bulk_received+=len-4;}}if(op==OP_ERROR)error_code=(p[2]<<8)|p[3];return len;}
ssize_t __wrap_sendto(int fd,const void *data,size_t len,int flags,const struct sockaddr *addr,socklen_t alen){
 const struct sockaddr_qrtr *peer=(const void *)addr;
 if(peer->sq_port==QRTR_PORT_CTRL && len==sizeof(struct qrtr_ctrl_pkt)){
  const struct qrtr_ctrl_pkt *packet=data;
  if(le32_to_cpu(packet->cmd)==QRTR_TYPE_NEW_SERVER){
   if(fail_publish && published==3){errno=EIO;return -1;}
   assert(published<10 && le32_to_cpu(packet->server.service)==4096);
   publication_keys[published]=le32_to_cpu(packet->server.instance);
   publication_ports[published]=le32_to_cpu(packet->server.port);published++;
  }
 }
 return len;
}
int __wrap_select(int nfds,fd_set *r,fd_set *w,fd_set *e,struct timeval *t){if(fail_select){errno=EIO;return -1;}if(select_last){for(int i=100;i<110;i++)assert(FD_ISSET(i,r));assert(nfds>=110);}FD_ZERO(r);FD_SET(select_last?109:100,r);return 1;}
ssize_t __wrap_recvfrom(int fd,void *buf,size_t len,int flags,struct sockaddr *addr,socklen_t *alen){
 last_listener=fd;
 struct sockaddr_qrtr q={.sq_family=AF_QIPCRTR,.sq_node=0,.sq_port=900};
 if(bulk_mode){unsigned char *p=buf;memcpy(addr,&q,sizeof(q));*alen=sizeof(q);p[0]=0;p[1]=OP_ACK;p[2]=last_block>>8;p[3]=last_block&255;return 4;}
 if(received++){errno=ENETRESET;return -1;}
 if(rx_case && !strcmp(rx_case,"listen-rx-rrq")) {
  memcpy(addr,&q,sizeof(q));*alen=sizeof(q);
  ((unsigned char*)buf)[0]=0;((unsigned char*)buf)[1]=OP_RRQ;return 2;
 }
 if(rx_case && !strcmp(rx_case,"listen-rx-short")) {
  memcpy(addr,&q,sizeof(q));*alen=sizeof(q);
  ((unsigned char*)buf)[0]=0xff;return 1;
 }
 memcpy(addr,&q,sizeof(q));*alen=sizeof(q);((unsigned char*)buf)[0]=0;((unsigned char*)buf)[1]=OP_ERROR;return 2;
}
static void cleanup_readers(void){struct tftp_client *p,*next;list_for_each_entry_safe(p,next,&readers,node)client_close_and_free(p);}
int main(int argc,char **argv){
 const char good[]={0,OP_RRQ,'/','r','e','a','d','o','n','l','y','/','f','i','r','m','w','a','r','e','/','i','m','a','g','e','/','w','l','a','n','m','d','s','p','.','m','b','n',0,'o','c','t','e','t',0};
 const char wrq[]="\0\2/readwrite/server_check.txt\0octet";
 const char denied[]="\0\1/readwrite/server_check.txt\0octet";
 struct sockaddr_qrtr peer={.sq_family=AF_QIPCRTR,.sq_node=0,.sq_port=900};
 if(argc!=3)return 90;
 if(!strncmp(argv[2],"listen-",7)){
  rx_case=argv[2];
  fail_publish=!strcmp(argv[2],"listen-publish-fail");fail_socket=!strcmp(argv[2],"listen-socket-fail");
  fail_select=!strcmp(argv[2],"listen-select-fail");high_socket=!strcmp(argv[2],"listen-high-fd");select_last=!strcmp(argv[2],"listen-last");
  char *args[]={"tqftpserv","-r",argv[1],NULL};int rc=upstream_main(3,args);
  printf("published=%u closed=%u sockets=%u last_listener=%d\n",published,closed_sockets,socket_calls,last_listener);
  if(fail_publish)return rc!=0 && published==3 && closed_sockets==4?0:101;
  if(fail_socket)return rc!=0 && published==3 && closed_sockets==3?0:102;
  if(high_socket)return rc!=0 && published==0 && closed_sockets==1?0:103;
  if(published!=10 || closed_sockets!=10)return 104;
  for(unsigned i=0;i<10;i++){if(publication_keys[i]!=i+1)return 105;for(unsigned j=0;j<i;j++)if(publication_ports[i]==publication_ports[j])return 106;}
  if(select_last && last_listener!=109)return 107;
  return (fail_select?rc!=0:rc==-ENETRESET)?0:108;
 }
 if(!strcmp(argv[2],"no-policy")){char *args[]={"tqftpserv",NULL};int rc=upstream_main(1,args);printf("socket_calls=%u\n",socket_calls);return rc!=0?0:90;}
 if(!strcmp(argv[2],"validate")){char *args[]={"tqftpserv","-r",argv[1],"-n",NULL};int rc=upstream_main(4,args);printf("socket_calls=%u\n",socket_calls);return rc;}
 if(!strcmp(argv[2],"short-error")){char *args[]={"tqftpserv","-r",argv[1],NULL};int rc=upstream_main(3,args);return rc==-ENETRESET?0:91;}
 if(translate_set_readonly_dir(argv[1])<0)return 92;
 if(!strcmp(argv[2],"rrq-bulk")){
  const char request[]="\0\1/readonly/firmware/image/wlanmdsp.mbn\0octet\0blksize\0" "7680\0wsize\0" "10\0rsize\0" "1048577\0seek\0" "0";
  bulk_mode=1;handle_rrq(request,sizeof(request),&peer);
  for(unsigned n=0;n<500 && readers.next!=&readers;n++){
   struct tftp_client *client=list_entry(readers.next,struct tftp_client,node);
   if(handle_reader(client)<=0){client_close_and_free(client);break;}
  }
  cleanup_readers();printf("bulk_received=%zu\n",bulk_received);return bulk_received==(1u<<20)+1?0:97;
 }
 if(!strcmp(argv[2],"huge-window")){
  const char request[]="\0\1/readonly/firmware/image/wlanmdsp.mbn\0octet\0blksize\0" "65464\0wsize\0" "65535";
  handle_rrq(request,sizeof(request),&peer);cleanup_readers();printf("large_allocations=%u\n",large_allocations);return error_code==TFTP_ERROR_EOPTNEG && large_allocations==0?0:98;
 }
 if(!strcmp(argv[2],"session-cap")){
  struct tftp_client *client;unsigned count=0;
  for(unsigned n=0;n<9;n++)handle_rrq(good,sizeof(good),&peer);
  list_for_each_entry(client,&readers,node)count++;
  cleanup_readers();printf("readers=%u\n",count);return count==8?0:99;
 }
 if(!strcmp(argv[2],"wrq")){handle_wrq(wrq,sizeof(wrq),&peer);printf("error_code=%u\n",error_code);return error_code==TFTP_ERROR_EACCESS?0:93;}
 if(!strcmp(argv[2],"wrq-long")){
  char big[420];size_t i;
  big[0]=0;big[1]=OP_WRQ;
  for(i=0;i<300;i++)big[2+i]='a';
  big[2+300]='\n';big[2+301]='\t';
  for(i=0;i<40;i++)big[2+302+i]='b';
  big[2+342]=0;memcpy(big+2+343,"octet",5);big[2+348]=0;
  handle_wrq(big,(size_t)(2+349),&peer);
  printf("error_code=%u\n",error_code);
  return error_code==TFTP_ERROR_EACCESS?0:95;
 }
 if(!strcmp(argv[2],"denied-rrq")){handle_rrq(denied,sizeof(denied),&peer);return error_code==TFTP_ERROR_EACCESS?0:94;}
 if(!strcmp(argv[2],"truncated-rrq")){for(size_t n=2;n<sizeof(good);n++){handle_rrq(good,n,&peer);assert(data_sends==0);cleanup_readers();}return 0;}
 if(!strcmp(argv[2],"rrq")){handle_rrq(good,sizeof(good),&peer);cleanup_readers();printf("data_sends=%u\n",data_sends);return data_sends==1?0:95;}
 return 96;
}

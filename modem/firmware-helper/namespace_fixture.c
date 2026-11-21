#define main pinned_nameserver_main
#include NS_SOURCE
#undef main
#include <assert.h>
static unsigned network_calls;
int __wrap_socket(int domain,int type,int protocol){network_calls++;assert(!"network forbidden");return -1;}
int __wrap_bind(int fd,const struct sockaddr *addr,socklen_t len){network_calls++;assert(!"network forbidden");return -1;}
ssize_t __wrap_sendto(int fd,const void *data,size_t len,int flags,const struct sockaddr *addr,socklen_t alen){network_calls++;assert(!"network forbidden");return -1;}
int main(int argc,char **argv){
 int unique=argc==2 && !strcmp(argv[1],"distinct");
 struct server_filter filter={.service=4096};
 struct list matches;
 assert(map_create(&nodes)==0);
 for(unsigned key=1;key<=10;key++)
  assert(server_add(4096,key,1,16000+(unique?key:0))!=NULL);
 int found=server_query(&filter,&matches);
 printf("namespace_count=%d network_calls=%u\n",found,network_calls);
 map_clear(&nodes,node_mi_free);map_destroy(&nodes);
 return found==(unique?10:1) && network_calls==0?0:1;
}

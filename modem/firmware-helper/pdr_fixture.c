// SPDX-License-Identifier: GPL-2.0
/* Offline transport fixture: no real QRTR socket or modem operation. */
#define main pdr_program_main
#include "pdr_restart.c"
#undef main
#include <assert.h>
#include <signal.h>

static const char *scenario;
static int sockets, connections, sends, closes, guards;
static unsigned char sent[2][128];
static size_t sizes[2];
int __wrap_socket(int family, int type, int protocol)
{
 assert(family == AF_QIPCRTR && type == SOCK_DGRAM && protocol == 0);
 if (!strcmp(scenario, "root-socket-fail")) { errno = EIO; return -1; }
 sockets++; return 99;
}
int __wrap_connect(int fd, const struct sockaddr *a, socklen_t n)
{
 const struct sockaddr_qrtr *q = (const void *)a;
 assert(fd == 99 && n == sizeof(*q) && q->sq_family == AF_QIPCRTR);
 assert(q->sq_node == 0 && q->sq_port == 1); connections++;
 if (!strcmp(scenario, "root-connect-fail")) { errno = EIO; return -1; }
 return 0;
}
int __wrap_setsockopt(int fd, int level, int opt, const void *v, socklen_t n)
{
 (void)v; (void)n;
 assert(fd == 99 && level == SOL_SOCKET && opt == SO_RCVTIMEO);
 if (!strcmp(scenario, "root-option-fail")) { errno = EIO; return -1; }
 return 0;
}
int __wrap_close(int fd) { assert(fd == 99); closes++; return 0; }
int __wrap_kill(pid_t pid, int sig)
{
 assert(pid == 4321 && sig == 0); guards++;
 if ((!strcmp(scenario, "dead-before") && guards == 1) ||
     (!strcmp(scenario, "dead-after") && guards == 2)) { errno = ESRCH; return -1; }
 return 0;
}
ssize_t __wrap_readlink(const char *p, char *b, size_t cap)
{
 const char *exe = !strcmp(scenario, "wrong-exe") ? "/bin/other" : "/tmp/provider";
 assert(!strcmp(p, "/proc/4321/exe") && cap > strlen(exe));
 memcpy(b, exe, strlen(exe)); return (ssize_t)strlen(exe);
}
ssize_t __wrap_send(int fd, const void *b, size_t n, int flags)
{
 assert(fd == 99 && flags == (!strncmp(scenario, "root-", 5) ? MSG_DONTWAIT : 0) && sends < 2 && n <= sizeof(sent[0]));
 if (!strncmp(scenario, "root-", 5)) {
  const unsigned char *q = b;
  assert(sends == 0 && q[3] == 0x21 && q[4] == 0);
  assert(n == 10 + strlen("msm/modem/root_pd") && !memcmp(q+10,"msm/modem/root_pd",n-10));
 }
 memcpy(sent[sends], b, n); sizes[sends++] = n;
 if (!strcmp(scenario, "root-send-fail")) { errno = EINTR; return -1; }
 if (!strcmp(scenario, "root-short-send")) return (ssize_t)n-1;
 return (ssize_t)n;
}
ssize_t __wrap_recv(int fd, void *b, size_t cap, int flags)
{
 unsigned char response[] = {2,1,0,0x20,0,14,0,2,4,0,0,0,0,0,0x10,4,0,0xff,0xff,0xff,0x0f};
 size_t n = sizeof(response);
 assert(fd == 99 && cap >= n && flags == (!strncmp(scenario, "root-", 5) ? MSG_TRUNC : 0) && sends > 0);
 if (!strncmp(scenario, "root-", 5)) {
  response[3] = 0x21; response[20] = 0x1f;
  if (!strcmp(scenario, "root-timeout")) { errno = EAGAIN; return -1; }
  if (!strcmp(scenario, "root-oversize")) return (ssize_t)cap+1;
  if (!strcmp(scenario, "root-wrong-txn")) response[1] = 9;
  if (!strcmp(scenario, "root-wrong-message")) response[3] = 0x24;
  if (!strcmp(scenario, "root-bad-tail")) response[15] = 50;
  if (!strcmp(scenario, "root-absent") || !strcmp(scenario, "root-refused")) { n=14; response[5]=7; }
  if (!strcmp(scenario, "root-refused")) { response[10]=1; response[12]=9; }
 }
 if (!strcmp(scenario, "timeout")) { errno = EAGAIN; return -1; }
 if (sends == 1 && !strcmp(scenario, "refused")) { response[10]=1; response[12]=9; }
 if (!strcmp(scenario, "wrong-txn")) response[1] = 9;
 if (!strcmp(scenario, "bad-tail")) response[15] = 50;
 if (!strcmp(scenario, "trailing")) response[5] = 7;
 if (sends == 2) {
  response[1]=2; response[3]=0x24; response[5]=7; n=14;
  if (!strcmp(scenario, "restart-refused")) { response[10]=1; response[12]=9; }
 }
 memcpy(b,response,n); return (ssize_t)n;
}
ssize_t __wrap_recvfrom(int fd, void *b, size_t cap, int flags,
                        struct sockaddr *addr, socklen_t *len)
{
 struct sockaddr_qrtr *q = (void *)addr;
 assert(!strncmp(scenario, "root-", 5) && *len == sizeof(*q));
 memset(q, 0, sizeof(*q)); q->sq_family=AF_QIPCRTR; q->sq_node=0; q->sq_port=1;
 if (!strcmp(scenario, "root-wrong-node")) q->sq_node=1;
 if (!strcmp(scenario, "root-wrong-port")) q->sq_port=2;
 if (!strcmp(scenario, "root-wrong-family")) q->sq_family=AF_UNIX;
 if (!strcmp(scenario, "root-short-peer")) *len=sizeof(*q)-1;
 return __wrap_recv(fd, b, cap, flags);
}
int main(int argc, char **argv)
{
 char *args[] = {"pdr_restart", "--listen-restart", "0", "1", "msm/modem/wlan_pd", "4321", "/tmp/provider", NULL};
 int rc;
 assert(argc == 2); scenario=argv[1];
 rc = !strncmp(scenario, "root-", 5)
  ? pdr_program_main(4, (char *[]){"pdr_restart", "--query-root", "0", "1", NULL})
  : pdr_program_main(7, args);
 printf("fixture rc=%d sockets=%d connections=%d sends=%d closes=%d guards=%d\n",rc,sockets,connections,sends,closes,guards);
 for (int i=0;i<sends;i++) { printf("frame%d=",i); print_hex(sent[i],sizes[i]); }
 assert(closes == sockets);
 return 0;
}

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
int main(int argc,char **argv){
 for(int i=1;i<argc;i++)if(!strcmp(argv[i],"-n"))return 0;
 const char *test=getenv("LIFE_CASE");
 if(test && !strcmp(test,"fail-start")){
  fputs("failed to open qrtr socket\n",stderr);return 2;
 }
 FILE *out=fopen(getenv("LIFE_STARTED"),"w");
 if(!out)return 3;
 fprintf(out,"%ld\n",(long)getpid());fclose(out);
 puts("readonly_firmware_open=accepted file=wlanmdsp.mbn");
 puts("readonly_spoof=private-identifier");fflush(stdout);
 for(;;)pause();
}

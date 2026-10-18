#define _GNU_SOURCE 1
/* Own process-only policy: legacy client cannot create sockets or resolve DNS
 * through a new Unix resolver socket. The dedicated :places process is not
 * filtered and exposes only a typed, non-exported location-to-places operation.
 * This is not a general-purpose sandbox against arbitrary malicious code. */
#include <errno.h>
#include <stddef.h>
#include <stdint.h>
#include <unistd.h>
#include <sys/prctl.h>
#include <sys/syscall.h>
#include <sys/socket.h>
#include <linux/audit.h>
#include <linux/filter.h>
#include <linux/seccomp.h>
#ifndef NZA_GUARD_TEST
#include <jni.h>
#endif

#if defined(__aarch64__)
#define NZA_ARCH AUDIT_ARCH_AARCH64
#elif defined(__x86_64__)
#define NZA_ARCH AUDIT_ARCH_X86_64
#elif defined(__arm__)
#define NZA_ARCH AUDIT_ARCH_ARM
#else
#error Unsupported policy architecture
#endif

#define DENY_NR(n) BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,(n),0,1), BPF_STMT(BPF_RET|BPF_K,SECCOMP_RET_ERRNO|EACCES)
int nza_install_network_guard(void) {
    static int installed;
    if(installed)return 0;
    struct sock_filter filter[]={
        BPF_STMT(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,arch)),
        BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,NZA_ARCH,1,0),
        BPF_STMT(BPF_RET|BPF_K,SECCOMP_RET_ERRNO|EACCES),
        BPF_STMT(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,nr)),
        DENY_NR(__NR_socket),
        DENY_NR(__NR_connect),
#ifdef __NR_socketcall
        DENY_NR(__NR_socketcall),
#endif
        /* Avoid a different socket-creation path on newer kernels. */
#ifdef __NR_io_uring_setup
        DENY_NR(__NR_io_uring_setup),
#endif
        BPF_STMT(BPF_RET|BPF_K,SECCOMP_RET_ALLOW)
    };
    struct sock_fprog program={sizeof(filter)/sizeof(filter[0]),filter};
    if(prctl(PR_SET_NO_NEW_PRIVS,1,0,0,0)!=0)return -errno;
    long result=syscall(__NR_seccomp,SECCOMP_SET_MODE_FILTER,SECCOMP_FILTER_FLAG_TSYNC,&program);
    if(result!=0)return result>0?-EBUSY:-errno;
    /* No test connects or DNS queries are sent. */
    for(unsigned i=0;i<3;i++) {
        int family=i==0?AF_INET:i==1?AF_INET6:AF_UNIX;
        errno=0;int fd=socket(family,SOCK_STREAM,0);
        if(fd>=0){close(fd);return -EPERM;}
        if(errno!=EACCES)return -EPERM;
    }
    installed=1;return 0;
}

#ifndef NZA_GUARD_TEST
JNIEXPORT jint JNICALL Java_com_ramsoc2_nzarevived_NzaNetworkGuard_installNative(JNIEnv* env,jclass type) {
    (void)env;(void)type;return nza_install_network_guard();
}
#else
#include <stdio.h>
#include <pthread.h>
static volatile int proceed;
static int existing_thread_blocked;
static void* worker(void* unused) {
    (void)unused;while(!proceed)usleep(1000);
    errno=0;int fd=socket(AF_INET,SOCK_STREAM,0);
    existing_thread_blocked=(fd<0&&errno==EACCES);
    if(fd>=0)close(fd);return 0;
}
int main(void) {
    pthread_t thread;if(pthread_create(&thread,0,worker,0))return 2;
    int result=nza_install_network_guard();proceed=1;pthread_join(thread,0);
    int pair[2];int local_pair=socketpair(AF_UNIX,SOCK_STREAM,0,pair)==0;
    if(local_pair){close(pair[0]);close(pair[1]);}
    printf("{\"install\":%d,\"existing_thread_denied\":%d,\"unix_socketpair_preserved\":%d}\n",result,existing_thread_blocked,local_pair);
    return result==0&&existing_thread_blocked&&local_pair?0:1;
}
#endif

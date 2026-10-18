#define _GNU_SOURCE 1
/* Private EXP-010: async-signal-safe SIGBUS capture; preserves the original fatal signal. */
#include <jni.h>
#include <fcntl.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sched.h>
#include <sys/syscall.h>
#include <sys/ucontext.h>
#include <unistd.h>

static volatile sig_atomic_t binary_fd=-1, maps_fd=-1;
static struct sigaction previous;
struct fault_record {
    char magic[8];
    uint64_t signal, code, pid, tid, address, pc, sp, pstate, regs[31];
};

static void capture(int signal, siginfo_t* info, void* raw) {
    const ucontext_t* context=(const ucontext_t*)raw;
    struct fault_record record={{'N','Z','A','H','F','0','0','1'},0};
    record.signal=(uint64_t)signal;record.code=(uint64_t)(int64_t)info->si_code;
    record.pid=(uint64_t)getpid();record.tid=(uint64_t)syscall(SYS_gettid);
    record.address=(uint64_t)(uintptr_t)info->si_addr;
    record.pc=context->uc_mcontext.pc;record.sp=context->uc_mcontext.sp;
    record.pstate=context->uc_mcontext.pstate;
    for(int i=0;i<31;++i)record.regs[i]=context->uc_mcontext.regs[i];
    if(binary_fd>=0) (void)write(binary_fd,&record,sizeof(record));
    int source=open("/proc/self/maps",O_RDONLY|O_CLOEXEC);
    if(source>=0 && maps_fd>=0){
        char block[4096];ssize_t count;
        while((count=read(source,block,sizeof(block)))>0)(void)write(maps_fd,block,(size_t)count);
    }
    if(source>=0)close(source);
    /* Return to the same faulting instruction under the original handler.
       Nothing skips the instruction or turns the crash into success. */
    (void)sigaction(signal,&previous,0);
}

JNIEXPORT jboolean JNICALL
Java_com_zettabridge_launcher_NzaHostFaultCapture_configure(JNIEnv* env,jclass cls,
                                                          jstring binary,jstring maps) {
    (void)cls;
    if(binary_fd>=0)return JNI_TRUE;
    const char* b=(*env)->GetStringUTFChars(env,binary,0);if(!b)return JNI_FALSE;
    int first=open(b,O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC,0600);
    /* Own-process diagnostic log; no logcat or other application data. */
    char log_path[512];
    int log_fd=-1;
    if(snprintf(log_path,sizeof(log_path),"%s.log",b)<(int)sizeof(log_path))
        log_fd=open(log_path,O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC,0600);
    if(log_fd>=0){dup2(log_fd,STDERR_FILENO);close(log_fd);}
#ifdef NZA_SINGLE_CPU
    cpu_set_t allowed,selected;CPU_ZERO(&allowed);CPU_ZERO(&selected);
    if(sched_getaffinity(0,sizeof(allowed),&allowed)==0) {
        int cpu=-1;
        for(int i=0;i<CPU_SETSIZE;++i)if(CPU_ISSET(i,&allowed))cpu=i;
        if(cpu>=0){CPU_SET(cpu,&selected);int rc=sched_setaffinity(0,sizeof(selected),&selected);
            dprintf(STDERR_FILENO,"NZA single-CPU diagnostic cpu=%d result=%d\n",cpu,rc);}
    }
#endif
#ifdef NZA_SYSCALL_TRACE
    setenv("ZB_STRACE","1",1);
#endif
    (*env)->ReleaseStringUTFChars(env,binary,b);
    if(first<0)return JNI_FALSE;
    const char* m=(*env)->GetStringUTFChars(env,maps,0);
    if(!m){close(first);return JNI_FALSE;}
    int second=open(m,O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC,0600);
    (*env)->ReleaseStringUTFChars(env,maps,m);
    if(second<0){close(first);return JNI_FALSE;}
    binary_fd=first;maps_fd=second;
    struct sigaction action={0};
    action.sa_sigaction=capture;action.sa_flags=SA_SIGINFO|SA_ONSTACK;
    sigemptyset(&action.sa_mask);
    return sigaction(SIGBUS,&action,&previous)==0?JNI_TRUE:JNI_FALSE;
}

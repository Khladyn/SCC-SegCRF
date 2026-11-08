# AVX2 sum of absolute differences of two byte buffers.
# Windows x64: rcx = a, rdx = b, r8 = count. Result in rax.
# 32 bytes per vpsadbw. The leftover bytes are added one at a time.

.intel_syntax noprefix
.text
.globl sad_avx2_asm
.globl _sad_avx2_asm

sad_avx2_asm:
_sad_avx2_asm:
    vpxor ymm0, ymm0, ymm0
    xor r10, r10
    mov r9, r8
    and r9, -32
    test r9, r9
    jz .Lfold

.Lloop:
    vmovdqu ymm1, ymmword ptr [rcx + r10]
    vmovdqu ymm2, ymmword ptr [rdx + r10]
    vpsadbw ymm1, ymm1, ymm2
    vpaddq ymm0, ymm0, ymm1
    add r10, 32
    cmp r10, r9
    jb .Lloop

.Lfold:
    vextracti128 xmm1, ymm0, 1
    vpaddq xmm0, xmm0, xmm1
    vpsrldq xmm1, xmm0, 8
    vpaddq xmm0, xmm0, xmm1
    vmovq rax, xmm0
    vzeroupper

.Ltail:
    cmp r10, r8
    jae .Ldone
    movzx r11d, byte ptr [rcx + r10]
    movzx r9d, byte ptr [rdx + r10]
    sub r11d, r9d
    movsxd r11, r11d
    mov r9, r11
    neg r11
    test r9, r9
    cmovns r11, r9
    add rax, r11
    inc r10
    jmp .Ltail

.Ldone:
    ret

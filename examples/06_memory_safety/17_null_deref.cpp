// 示例17：空指针解引用崩溃 (Null Pointer Dereference)
#include <iostream>
using namespace std;

int main() {
    // 显式设为 nullptr
    int* p = nullptr;

    cout << "p = " << p << endl;

    // 解引用 nullptr —— 写入地址 0x0
    // 操作系统保护'零页'，触发 Segmentation Fault
    *p = 100;

    return 0;
}

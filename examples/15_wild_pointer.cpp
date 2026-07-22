// 示例15：野指针崩溃 (Wild Pointer)
#include <iostream>
using namespace std;

int main() {
    // int* p 未初始化 —— 值是随机的"垃圾地址"
    int* p;

    // 试图 delete 一个从未初始化的指针
    // 运行时会立刻崩溃：Segmentation Fault
    delete p;

    return 0;
}

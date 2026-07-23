// 示例4：堆内存 new / delete
#include <iostream>
using namespace std;

int main() {
    // 在堆上分配一个 int
    int* p = new int;
    *p = 99;

    cout << "堆上的值: " << *p << endl;

    // 释放内存
    delete p;

    // 分配数组
    int* arr = new int[3];
    delete arr;

    return 0;
}

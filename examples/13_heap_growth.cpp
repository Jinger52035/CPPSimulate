// 示例13：堆向高地址增长
#include <iostream>
using namespace std;

int main() {
    // 连续 new，观察地址递增方向
    int* a = new int;
    int* b = new int;
    int* c = new int;
    int* d = new int;

    *a = 10;
    *b = 20;
    *c = 30;
    *d = 40;

    cout << "a = " << *a << "  addr=" << a << endl;
    cout << "b = " << *b << "  addr=" << b << endl;
    cout << "c = " << *c << "  addr=" << c << endl;
    cout << "d = " << *d << "  addr=" << d << endl;

    // 释放顺序与分配顺序无关
    delete b;
    delete a;
    delete d;
    delete c;

    return 0;
}

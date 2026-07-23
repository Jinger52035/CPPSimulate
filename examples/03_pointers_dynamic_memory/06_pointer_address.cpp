// 示例6：指针与地址
#include <iostream>
using namespace std;

int main() {
    int x = 42;
    int y = 100;

    int* p = &x;
    cout << "x = " << x << endl;

    *p = 99;
    cout << "x after *p=99: " << x << endl;

    p = &y;
    *p = 200;
    cout << "y after *p=200: " << y << endl;

    return 0;
}

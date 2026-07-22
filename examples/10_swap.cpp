// 示例10：值传递 vs 指针传递
#include <iostream>
using namespace std;

void swapByValue(int a, int b) {
    int tmp = a;
    a = b;
    b = tmp;
}

void swapByPtr(int* a, int* b) {
    int tmp = *a;
    *a = *b;
    *b = tmp;
}

int main() {
    int x = 10;
    int y = 20;

    swapByValue(x, y);
    cout << "after swapByValue: x=" << x << " y=" << y << endl;

    swapByPtr(&x, &y);
    cout << "after swapByPtr: x=" << x << " y=" << y << endl;

    return 0;
}

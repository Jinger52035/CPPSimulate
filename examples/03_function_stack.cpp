// 示例3：函数调用与栈帧
#include <iostream>
using namespace std;

int multiply(int a, int b) {
    int result = a * b;
    return result;
}

int add(int x, int y) {
    int r = x + y;
    return r;
}

int main() {
    int p = multiply(4, 5);
    int q = add(p, 3);

    cout << "p = " << p << endl;
    cout << "q = " << q << endl;
    return 0;
}

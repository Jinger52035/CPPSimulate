// 示例8：作用域与变量遮蔽
#include <iostream>
using namespace std;

int x = 10;

void modify() {
    int x = 99;
    x += 1;
    cout << "local x = " << x << endl;
}

int main() {
    cout << "global x = " << x << endl;
    modify();
    cout << "global x after modify = " << x << endl;

    int x = 50;
    x += 5;
    cout << "main local x = " << x << endl;

    return 0;
}

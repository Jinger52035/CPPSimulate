// 示例14：数据段、BSS段与常量区
#include <iostream>
using namespace std;

// 已初始化全局变量 → 数据段 (Data)
int globalCount = 42;
float globalPi = 3.14;

// 未初始化全局变量 → BSS 段
int globalUnset;

int main() {
    globalCount = 100;
    globalUnset = 7;

    cout << "globalCount = " << globalCount << endl;
    cout << "globalPi = " << globalPi << endl;
    cout << "globalUnset = " << globalUnset << endl;

    return 0;
}

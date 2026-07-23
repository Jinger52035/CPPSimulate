// 示例16：二次释放崩溃 (Double Free)
#include <iostream>
using namespace std;

int main() {
    // 正常分配
    int* p = new int;
    *p = 42;

    cout << "p = " << *p << endl;

    // 第一次 delete：正常释放堆内存
    // 此后 p 变为悬空指针（dangling pointer）
    delete p;

    // 第二次 delete 同一地址 —— 崩溃！
    // 堆管理器的元数据链表已损坏
    delete p;

    return 0;
}

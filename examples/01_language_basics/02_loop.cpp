// 示例2：for 循环 —— 累加求和
#include <iostream>
using namespace std;

int main() {
    int sum = 0;

    for (int i = 1; i <= 5; i++) {
        sum += i;
        cout << "i=" << i << " sum=" << sum << endl;
    }

    cout << "1+2+3+4+5 = " << sum << endl;
    return 0;
}

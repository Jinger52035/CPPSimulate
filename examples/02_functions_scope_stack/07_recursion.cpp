// 示例7：递归与栈帧增长
#include <iostream>
using namespace std;

int factorial(int n) {
    if (n <= 1) {
        return 1;
    }
    int sub = factorial(n - 1);
    int result = n * sub;
    return result;
}

int main() {
    int n = 4;
    int ans = factorial(n);
    cout << "4! = " << ans << endl;
    return 0;
}

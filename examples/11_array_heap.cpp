// 示例11：堆上分配数组
#include <iostream>
using namespace std;

int main() {
    int n = 5;
    int* arr = new int[5];

    arr[0] = 10;
    arr[1] = 20;
    arr[2] = 30;

    int sum = 0;
    for (int i = 0; i < 3; i++) {
        sum += arr[i];
    }

    cout << "sum = " << sum << endl;

    delete[] arr;
    return 0;
}

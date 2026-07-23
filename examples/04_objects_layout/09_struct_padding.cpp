// 示例9：结构体内存对齐与 padding
#include <iostream>
using namespace std;

class Packed {
public:
    char a;
    int  b;
    char c;
    double d;

    Packed(char a, int b, char c, double d) {
        this->a = a;
        this->b = b;
        this->c = c;
        this->d = d;
    }
};

int main() {
    Packed obj('X', 42, 'Y', 3.14);
    cout << "a = " << obj.a << endl;
    cout << "b = " << obj.b << endl;
    cout << "d = " << obj.d << endl;
    return 0;
}

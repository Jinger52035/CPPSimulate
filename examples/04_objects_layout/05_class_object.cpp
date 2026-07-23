// 示例5：类的实例化与销毁
#include <iostream>
using namespace std;

class Rectangle {
public:
    char label;
    int area;
    char flag;

    Rectangle(char l, char f, int a) {
        label = l;
        flag = f;
        area = a;
        cout << "构造: Rectangle('" << label << "', '" << flag << "', " << area << ")" << endl;
    }

    ~Rectangle() {
        cout << "析构: Rectangle('" << label << "')" << endl;
    }
};

int main() {
    Rectangle r1('A', 'X', 12);
    cout << "area: " << r1.area << endl;

    Rectangle r2('B', 'Y', 30);
    cout << "area: " << r2.area << endl;

    return 0;
}

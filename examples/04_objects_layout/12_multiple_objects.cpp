// 示例12：多个对象的构造与析构顺序
#include <iostream>
using namespace std;

class Point {
public:
    int x;
    int y;

    Point(int x, int y) {
        this->x = x;
        this->y = y;
        cout << "Point(" << x << ", " << y << ") constructed" << endl;
    }

    ~Point() {
        cout << "Point(" << x << ") destroyed" << endl;
    }
};

int main() {
    Point p1(1, 2);
    Point p2(3, 4);
    Point p3(5, 6);

    p1.x = 100;
    cout << "p1.x = " << p1.x << endl;

    return 0;
}

// 示例18：vector 基本操作与内存可视化
// 展示 vector 的连续内存分配、动态扩容机制
#include <vector>
using namespace std;

int main()
{
    // 声明一个空 vector
    vector<int> v;

    // push_back 逐个追加元素
    v.push_back(10);
    v.push_back(20);
    v.push_back(30);
    v.push_back(40);

    // 读取 size
    int s = v.size();

    // 下标访问
    int first = v[0];
    int last  = v.back();

    // 花括号初始化
    vector<int> nums = {2, 7, 11, 15};
    int n = nums.size();

    return 0;
}

// 示例19：unordered_map 哈希表操作
// 展示 Two Sum 核心算法的哈希表查找逻辑
#include <vector>
#include <unordered_map>
using namespace std;

int main()
{
    // 输入数据
    vector<int> nums = {2, 7, 11, 15};
    int target = 9;

    // 哈希表：value -> index
    unordered_map<int, int> hashtable;

    for (int i = 0; i < nums.size(); ++i) {
        // 查找 target - nums[i] 是否已经在表中
        auto it = hashtable.find(target - nums[i]);
        if (it != hashtable.end()) {
            // 找到！返回两个下标
            return 1;
        }
        // 未找到，将当前元素加入哈希表
        hashtable[nums[i]] = i;
    }

    return 0;
}

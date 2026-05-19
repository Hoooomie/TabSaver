// TabSaver - Domain Categories Mapping
// 域名分类映射表，用于专注力报告中的分类统计

const DOMAIN_CATEGORIES = {
  'Social': [
    'weibo.com', 'weibo.cn', 'twitter.com', 'x.com', 'facebook.com',
    'instagram.com', 'reddit.com', 'zhihu.com', 'douban.com',
    'xiaohongshu.com', 'linkedin.com', 'tiktok.com', 'douyin.com'
  ],
  'Development': [
    'github.com', 'gitlab.com', 'stackoverflow.com', 'stackexchange.com',
    'npmjs.com', 'pypi.org', 'docs.rs', 'crates.io', 'hub.docker.com',
    'developer.mozilla.org', 'devdocs.io', 'codepen.io', 'codesandbox.io',
    'leetcode.com', 'leetcode.cn', 'codeforces.com', 'nuist.edu.cn'
  ],
  'Communication': [
    'mail.google.com', 'outlook.live.com', 'outlook.office.com',
    'slack.com', 'discord.com', 'teams.microsoft.com', 'web.wechat.com',
    't.me', 'web.telegram.org', 'qq.com', 'mail.qq.com'
  ],
  'Entertainment': [
    'youtube.com', 'youtu.be', 'netflix.com', 'bilibili.com',
    'twitch.tv', 'spotify.com', 'music.163.com', 'iqiyi.com',
    'youku.com', 'mgtv.com', 'acfun.cn', 'steam.com', 'store.steampowered.com'
  ],
  'News': [
    'news.ycombinator.com', 'bbc.com', 'cnn.com', 'reuters.com',
    'theguardian.com', 'nytimes.com', '36kr.com', 'ifeng.com',
    'thepaper.cn', 'jiemian.com', 'chinadaily.com.cn'
  ],
  'Work': [
    'notion.so', 'notion.site', 'jira.com', 'atlassian.net',
    'confluence.com', 'figma.com', 'docs.google.com', 'sheets.google.com',
    'slides.google.com', 'docs.qq.com', 'kdocs.cn', 'feishu.cn',
    'dingtalk.com', 'yuque.com'
  ],
  'Shopping': [
    'taobao.com', 'tmall.com', 'jd.com', 'amazon.com', 'amazon.cn',
    'pinduoduo.com', 'suning.com', 'dangdang.com'
  ],
  'Learning': [
    'coursera.org', 'udemy.com', 'edx.org', 'khanacademy.org',
    'mooc.cn', 'icourse163.org', 'runoob.com', 'w3schools.com'
  ]
};

/**
 * 根据域名获取分类
 * @param {string} domain - 如 "github.com"
 * @returns {string} 分类名，未匹配返回 "Other"
 */
function getCategoryForDomain(domain) {
  if (!domain) return 'Other';
  for (const [category, domains] of Object.entries(DOMAIN_CATEGORIES)) {
    for (const d of domains) {
      // 精确匹配 或 子域名匹配 (e.g., mail.google.com 匹配 google.com)
      if (domain === d || domain.endsWith('.' + d)) {
        return category;
      }
    }
  }
  return 'Other';
}

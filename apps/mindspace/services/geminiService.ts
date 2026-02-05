// Gemini Service - 获取每日引言
// TODO: 集成实际的 Gemini API

export async function getDailyQuote(): Promise<string> {
    // 占位符实现，返回默认引言
    const quotes = [
        "心静自然凉",
        "活在当下",
        "每一天都是新的开始",
        "内心的平静是最大的财富",
        "慢下来，感受生活"
    ];
    return quotes[Math.floor(Math.random() * quotes.length)];
}

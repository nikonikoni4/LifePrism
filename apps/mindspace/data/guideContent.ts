
export interface GuideSection {
  id: string;
  title: string;
  content?: string;
  subsections?: GuideSection[];
}

export const GUIDE_DATA: Record<string, GuideSection[]> = {
  'main': [
    {
      id: 'mood',
      title: 'Mood · 心情',
      content: `
        <h3 class="font-serif text-2xl mb-4 text-[#2c3e50]">Understanding Your Emotional Landscape</h3>
        <p class="mb-6 leading-relaxed text-slate-600 font-light">
          Mood tracking is more than just recording if you are happy or sad. It is about observing the subtle shifts in your internal weather. 
          By consistently tracking your mood, you can identify triggers, patterns, and cycles that influence your well-being.
        </p>
        <p class="mb-6 leading-relaxed text-slate-600 font-light">
          <strong class="text-[#c9a063]">How to use:</strong> Select the emotion that best resonates with your current state. 
          Don't judge the feeling; simply acknowledge it. "Name it to tame it."
        </p>
      `
    },
    {
      id: 'journal',
      title: 'Journal · 日记',
      content: `
        <h3 class="font-serif text-2xl mb-4 text-[#2c3e50]">The Art of Reflection</h3>
        <p class="mb-6 leading-relaxed text-slate-600 font-light">
          Journaling serves as a safe container for your thoughts. It allows you to externalize the chaos of the mind onto a structured medium.
        </p>
        <ul class="list-disc pl-5 space-y-2 text-slate-600 font-light mb-6">
          <li><strong>Free Writing:</strong> Write without stopping or editing.</li>
          <li><strong>Gratitude:</strong> List three things you are thankful for.</li>
          <li><strong>Structured Reflection:</strong> Use prompts to guide your thinking.</li>
        </ul>
      `
    },
    {
      id: 'being',
      title: 'Being · 存在',
      content: `
        <h3 class="font-serif text-2xl mb-4 text-[#2c3e50]">Simply Existing</h3>
        <p class="mb-6 leading-relaxed text-slate-600 font-light">
          The "Being" module is the heart of Mind Space. It challenges the modern obsession with "Doing." 
          It allows you to explore the continuum of self across time.
        </p>
      `,
      subsections: [
        {
          id: 'who-was-i',
          title: 'Who Was I · 逝者如斯',
          content: `
            <h4 class="font-bold text-xl mb-3 text-slate-800">Reconcile with the Past</h4>
            <p class="mb-4 leading-relaxed text-slate-600 font-light">
              "Who Was I" is not about nostalgia; it is about integration. We look back not to stay there, but to understand the foundations of our current self.
            </p>
          `,
          subsections: [
            {
              id: 'reinterpret-past',
              title: 'Reinterpret Past · 积极重构',
              content: `
                <h4 class="font-bold text-xl mb-3 text-[#c9a063]">Alchemy of Memory</h4>
                <p class="mb-4 leading-relaxed text-slate-600 font-light">
                  Positive Reinterpretation (积极重构) is a cognitive technique to shift your perspective on past negative events.
                  It transforms "trauma" into "resilience".
                </p>
                <div class="bg-slate-50 p-6 rounded-xl border border-slate-100 mb-6">
                  <h5 class="font-bold text-sm uppercase tracking-widest text-slate-400 mb-4">The 3-Step Process</h5>
                  <ol class="space-y-4 list-decimal pl-4 text-slate-700">
                    <li>
                      <strong>Confront the Shadow:</strong> Identify a specific past event that still brings up negative emotions.
                    </li>
                    <li>
                      <strong>Find the Gold:</strong> Ask yourself, "What strength did I develop because of this?" or "What did I learn that I wouldn't have known otherwise?"
                    </li>
                    <li>
                      <strong>Project Forward:</strong> Use this new strength to guide your future actions.
                    </li>
                  </ol>
                </div>
                <p class="text-sm text-slate-500 italic">
                  Note: This does not mean denying the pain of the past, but rather finding meaning within it.
                </p>
              `
            }
          ]
        },
        {
          id: 'who-am-i',
          title: 'Who Am I · 当下',
          content: `
             <h4 class="font-bold text-xl mb-3 text-slate-800">Grounding in the Now</h4>
             <p class="text-slate-600 font-light">A scan of your current state: Identity, Time, Space, and Emotion.</p>
          `
        },
        {
          id: 'who-will-i-be',
          title: 'Who Will I Be · 愿景',
          content: `
             <h4 class="font-bold text-xl mb-3 text-slate-800">Intentional Future</h4>
             <p class="text-slate-600 font-light">Setting a compassionate intention for the person you are becoming.</p>
          `
        }
      ]
    }
  ]
};

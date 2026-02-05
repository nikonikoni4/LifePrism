
export const MOCK_ENTRIES = [
  {
    id: 1715411200000,
    timestamp: new Date(new Date().setDate(new Date().getDate() - 8)).setHours(9, 30),
    mood: { id: 'joy', icon: 'Sun', color: '#fed7aa', text: '喜悦', score: 90, isDark: false },
    impacts: ['Weather', 'Coffee', 'Music'],
    note: 'The morning sun is gentle. Had a great cup of coffee and listened to my favorite jazz playlist. Feeling energized for the day ahead.',
    stats: {
      screenTime: { work: 6.5, entertainment: 1.5, other: 0.5 },
      sleep: 7.2
    }
  },
  {
    id: 1715504800000,
    timestamp: new Date(new Date().setDate(new Date().getDate() - 7)).setHours(14, 15),
    mood: { id: 'calm', icon: 'Wind', color: '#d1fae5', text: '宁静', score: 70, isDark: false },
    impacts: ['Reading', 'Park'],
    note: 'Spent the afternoon reading in the park. The breeze was perfect. Felt a deep sense of peace.',
    stats: {
      screenTime: { work: 4.0, entertainment: 3.0, other: 1.0 },
      sleep: 8.0
    }
  },
  {
    id: 1715594800000,
    timestamp: new Date(new Date().setDate(new Date().getDate() - 6)).setHours(19, 20),
    mood: { id: 'pensive', icon: 'Cloud', color: '#cbd5e1', text: '沉思', score: 50, isDark: false },
    impacts: ['Work', 'Future'],
    note: 'Thinking a lot about my career path today. It’s not bad, just... uncertain. Need to reflect more on what I really want.',
    stats: {
      screenTime: { work: 8.5, entertainment: 0.5, other: 1.5 },
      sleep: 6.5
    }
  },
  {
    id: 1715681200000,
    timestamp: new Date(new Date().setDate(new Date().getDate() - 5)).setHours(8, 0),
    mood: { id: 'melancholy', icon: 'Moon', color: '#a5b4fc', text: '忧郁', score: 30, isDark: false },
    impacts: ['Sleep', 'Dream'],
    note: 'Woke up feeling a bit heavy. Had a strange dream that lingered. It’s okay to not be okay sometimes.',
    stats: {
      screenTime: { work: 5.0, entertainment: 4.0, other: 2.0 },
      sleep: 5.5
    }
  },
  {
    id: 1715767600000,
    timestamp: new Date(new Date().setDate(new Date().getDate() - 4)).setHours(21, 45),
    mood: { id: 'joy', icon: 'Sun', color: '#fed7aa', text: '喜悦', score: 85, isDark: false },
    impacts: ['Friends', 'Dinner'],
    note: 'Dinner with old friends. Laughed until my stomach hurt. Connection is everything.',
    stats: {
      screenTime: { work: 7.0, entertainment: 2.5, other: 0.5 },
      sleep: 7.0
    }
  },
  {
    id: 1715854000000,
    timestamp: new Date(new Date().setDate(new Date().getDate() - 3)).setHours(10, 0),
    mood: { id: 'calm', icon: 'Wind', color: '#d1fae5', text: '宁静', score: 75, isDark: false },
    impacts: ['Meditation'],
    note: 'Morning meditation session went deep. Found a quiet space within myself.',
    stats: {
      screenTime: { work: 4.5, entertainment: 1.0, other: 1.0 },
      sleep: 8.5
    }
  },
  {
    id: 1715940400000,
    timestamp: new Date(new Date().setDate(new Date().getDate() - 2)).setHours(16, 30),
    mood: { id: 'anger', icon: 'Flame', color: '#fb7185', text: '愤怒', score: 40, isDark: true },
    impacts: ['Traffic', 'Delay'],
    note: 'Stuck in traffic for hours. Missed the appointment. Frustrated beyond belief, but breathing through it.',
    stats: {
      screenTime: { work: 9.0, entertainment: 0.5, other: 2.5 },
      sleep: 6.0
    }
  },
  {
    id: 1716026800000,
    timestamp: new Date(new Date().setDate(new Date().getDate() - 1)).setHours(12, 0),
    mood: { id: 'joy', icon: 'Sun', color: '#fed7aa', text: '喜悦', score: 95, isDark: false },
    impacts: ['Hiking', 'Nature'],
    note: 'Reached the summit! The view is breathtaking. Worth every step.',
    stats: {
      screenTime: { work: 0.0, entertainment: 5.0, other: 1.0 },
      sleep: 9.0
    }
  },
   {
    id: 1716113200000,
    timestamp: new Date().setHours(20, 0),
    mood: { id: 'calm', icon: 'Wind', color: '#d1fae5', text: '宁静', score: 72, isDark: false },
    impacts: ['Bath', 'Self-care'],
    note: 'Relaxing bath to end the week. ready for Monday.',
    stats: {
      screenTime: { work: 2.0, entertainment: 3.5, other: 1.5 },
      sleep: 8.0
    }
  },
];

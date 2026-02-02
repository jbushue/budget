// Formatting utilities

export const formatCurrency = (value: number): string => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
};

export const formatDate = (date: Date): string => {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(date);
};

export const formatDateShort = (date: Date): string => {
  return new Intl.DateTimeFormat('en-US', {
    month: '2-digit',
    day: '2-digit',
  }).format(date);
};

export const formatPercent = (value: number, decimals: number = 1): string => {
  return `${(value * 100).toFixed(decimals)}%`;
};

export const formatCompactNumber = (value: number): string => {
  if (value >= 1000000) {
    return `$${(value / 1000000).toFixed(1)}M`;
  }
  if (value >= 1000) {
    return `$${(value / 1000).toFixed(1)}K`;
  }
  return formatCurrency(value);
};

export const getFrequencyLabel = (frequency: string): string => {
  const labels: { [key: string]: string } = {
    weekly: 'Every Week',
    biweekly: 'Every 2 Weeks',
    semimonthly: 'Twice Monthly',
    monthly: 'Monthly',
    quarterly: 'Quarterly',
    semi_annual: 'Every 6 Months',
    yearly: 'Yearly',
  };
  return labels[frequency] || frequency;
};

export const getDayLabel = (day: number): string => {
  if (day === 1) return '1st';
  if (day === 2) return '2nd';
  if (day === 3) return '3rd';
  if (day >= 21) return `${day}st`;
  if (day >= 11 && day <= 13) return `${day}th`;
  return `${day}th`;
};

export const getMonthsArray = (months: number): string[] => {
  const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const result = [];
  const currentMonth = new Date().getMonth();
  for (let i = 0; i < months; i++) {
    result.push(monthNames[(currentMonth + i) % 12]);
  }
  return result;
};

export const calculateTrendPercentage = (current: number, previous: number): number => {
  if (previous === 0) return 0;
  return ((current - previous) / Math.abs(previous)) * 100;
};


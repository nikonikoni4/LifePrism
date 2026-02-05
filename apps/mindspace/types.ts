import React from 'react';

export interface FeatureItem {
  id: string;
  title: string;
  description: string;
  icon: React.ElementType;
  color: string;
  delay: number;
}

export interface QuoteResponse {
  quote: string;
  author: string;
}
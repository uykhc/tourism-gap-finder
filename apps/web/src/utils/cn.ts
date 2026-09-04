import { type ClassValue, clsx } from 'clsx';
import { extendTailwindMerge } from 'tailwind-merge';

const mergeClassNames = extendTailwindMerge({
  extend: {
    theme: {
      text: [
        'heading',
        'subheading',
        'body',
        'body-strong',
        'body-small',
        'label',
        'label-small',
      ],
    },
  },
});

export const cn = (...inputs: ClassValue[]) => mergeClassNames(clsx(inputs));

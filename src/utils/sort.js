import { isThisNumber } from './detectDataType.js';

export const ascending = ( array ) => {
	if (!(array)) return;
	// 오름차순
	const data = array;

	if (typeof(data) === 'number') {
		return [...data].sort((a, b) => a - b);
	}

	return [...data].sort();
};

export const descending = ( array ) => {
	if (!(array)) return;
	// 내림차순
	const data = array;

	if (typeof(data) === 'number') {
		return [...data].sort((a, b) => b - a);
	}

	return [...data].reverse();
};
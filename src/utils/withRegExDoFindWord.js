export const findExactWordByRegEx = ( origin, originRegex ) => {
	if (!origin) return '';

	const inputString = origin;
	const regex = originRegex;
	
	const match = inputString.match(regex);

	if (!match) return null;

	return match[0];
};


export const findAfterWordByRegEx = ( origin, originRegex ) => {
	if (!origin) return '';
	// console.log('origin', origin, 'regex', originRegex);

	const inputString = origin;
	const regex = originRegex;
	
	const match = inputString.match(regex);

	if (!match) return null;

	// console.info('Input string : ', match[0]);

	return match[1];
};


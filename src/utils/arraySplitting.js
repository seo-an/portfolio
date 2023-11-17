export const arraySplitting = (array, num) => {
	const data = array;
	const devidedBy = num;
	const newArray = [];

	const splitting = (data, devidedBy) => {

		if (data.length < devidedBy) return newArray.push(data);

		const arry = data.slice(0, devidedBy);
		const rest = data.slice(devidedBy, data.length);

		newArray.push(arry);

		if (rest.length === 0) return;

		return splitting(rest, devidedBy);
	}

	splitting(data, devidedBy);
	
	return newArray;
};
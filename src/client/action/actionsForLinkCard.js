export const handleClickDiv = (e) => {
	if (e.target.querySelector('a') === null) return;

	else if (e.target.querySelector('a').tagName === 'A') {
		e.preventDefault();
		const href = e.target.querySelector('a').getAttribute('href');
		// window.open(href);
		window.location.href = href;
		return;
	}
	
}
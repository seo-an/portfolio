import { LinkCardsView } from "../../view/pages/LinkCardsView";

export const LinkCardsJs = () => {
	const data = [
		{
			id: `calendar`,
			link: `/calendar`,
			text: '캘린더'
		},
		{
			id: `svg-component`,
			link: `/svg-component`,
			text: '컴포넌트형 SVG'
		}
	];

	return (
		<LinkCardsView props = { { data } }/>
	);
}
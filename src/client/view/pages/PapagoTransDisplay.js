export const PapagoTransDisplay = ( props ) => {
	// console.log('디스플레이', props.original, props.translated);

	return (
		props.original && props.translated ? <p>원문: {props.original} | 번역: {props.translated}</p> : <p>번역할 내용이 없습니다.</p>
	)
};
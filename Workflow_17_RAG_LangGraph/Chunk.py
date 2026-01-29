def get_chunk(text: str, chunk_size: int = 3, overlap: int = 2):
    chunks = []
    text_size = len(text)

    base_size = text_size // chunk_size

    for i in range(chunk_size):
        # normal boundaries
        start = i * base_size
        end = (i + 1) * base_size if i < chunk_size - 1 else text_size

        # apply overlap (except first chunk)
        if i != 0:
            start = max(0, start - overlap)

        chunks.append(text[start:end])
        print(f"chunk {i}: start={start}, end={end}")

    return chunks


text = "Machine learning and Artificial Intelligence is part of Data Science. The above skill is Gen AI in this field. Generative AI is the era changing invenstion."
vector_store = get_chunk(text, 3, 5)
print(vector_store)

import Heurist from 'heurist'

const heurist = new Heurist({
  apiKey: process.env['HEURIST_API_KEY'],
})

async function main() {
  console.log('Starting image generation...')
  try {
    const response = await heurist.images.generate({
      model: 'BrainDance',
      prompt: 'a apple',
      width: 512,
      height: 512
    })
    const { url } = response
    console.log('Image generation successful!')
    console.log('Generated image URL:', url)
  } catch (error) {
    console.error('Error generating image:', error.message)
  }
}

main()
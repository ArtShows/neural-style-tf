from shutil import which
import sys 
import argparse 
import os
from os import path
import subprocess
import pathlib
import re
import glob
import signal
import zlib
import types
import json
from termcolor import colored, cprint
import colorama
colorama.init()



def get_screen_width():
  columns,lines = os.get_terminal_size() 
  return columns

os.environ["COLUMNS"] = str(get_screen_width())

'''
  parsing and configuration
'''
def parse_args():

  
  desc = "Sylize video tool for 'A Neural Algorithm for Artistic Style'" 
  parser = argparse.ArgumentParser(
    # formatter_class=argparse.RawTextHelpFormatter,
    formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    description=desc
  ) 
  
  parser.add_argument('--style_imgs_weights', nargs='+', type=float,
    default=[1.0],
    help='Interpolation weights of each of the style images. (example: 0.5 0.5)')
  
  parser.add_argument('--verbose', type=int, 
    default=1,
    choices=[0,1,2],
    help='Integer indicating granularity of information to be printed to the console. 0=None, 2=Most')
    
    
  parser.add_argument('--gpu', type=int, 
    default=0,
    help='Use a specific gpu if multiple are available.')
    
  parser.add_argument('--output_extension', type=int, 
    help='Choose a specific extension to output the combined frames to. (Default: match input)')
    
    
  parser.add_argument('-dirlen', '--max_output_dir_name_length', type=int, 
    default=180,
    help='Max size for output directory name. Larger names will be hashed to fit desired length and prevent collision.')
    
  parser.add_argument('-ef', '--end_frame', type=int, 
    help='Frame to stop rendering at')
    
  parser.add_argument('-ms', '--max_size', type=int, 
    help='Max size to resize input video\' longest edge to')
  
  parser.add_argument('media', type=str, nargs='+',
                    help='list of media, 1 input and 1 or more styles to apply')
  
  parser.add_argument('--interlaced', action='store_true',
    default=False,
    help='Boolean flag indicating if source video is interlaced.')
  
  parser.add_argument('--overwrite_image_sequence_video', action='store_true',
    default=False,
    help='Boolean flag indicating if it\'s okay to overwrite a previously rendered video of stylized images')

  parser.add_argument('--', type=str, nargs='*',
    dest='additional_args',
    help="Extra arguments to be passed along to neural_style.py. Ex: " + colored("-- --first_frame_iterations 600 --frame_iterations 200", 'yellow') 
  )
  
  # Separate out additional arguments to be sent along to neural_style.py
  inputArgs = sys.argv[1:]
  additional_args_pos = next((i for i,v in enumerate(sys.argv) if v.lower() == '--'), False)
  additional_args=[]
  if( additional_args_pos is not False ):
    inputArgs = sys.argv[1:additional_args_pos]
    additional_args = sys.argv[additional_args_pos+1:]
    
    
  # Parse the args
  args = parser.parse_args(inputArgs)  
  if args.verbose: print('parsed args:',args)
  
  
  # Overwrite the additional_args with the real list
  args.additional_args = additional_args
  
  
  
  if ( len(args.media) < 2 ):
     nprint("Media list missing style or \"skiprender\" flag!")
     print("Found only: " + " ".join(args.media) )
     nprint("")
     parser.print_help()
     sys.exit(1)
     
  
  
  args.skipflow = 	("skipflow" in (i.lower() for i in args.media)) if len(args.media) > 2 else False
  if args.verbose: print('skipflow:',args.skipflow)
  args.skiprender = 	("skiprender" in (i.lower() for i in args.media)) if len(args.media) > 1 else False
  if args.verbose: print('skiprender:',args.skiprender)

  # # echo ""
  # # read -p "Did you install the required dependencies? [y/n] $cr > " dependencies

  # # if [ "$dependencies" != "y" ] then
    # # echo "Error: Requires dependencies: tensorflow, opencv2 (python), scipy"
    # # exit 1
  # # fi

  # # echo ""
  # # read -p "Do you have a CUDA enabled GPU? [y/n] $cr > " cuda

  # # if [ "$cuda" != "y" ] then
    # # echo "Error: GPU required to render videos in a feasible amount of time."
    # # exit 1
  # # fi


  # Parse args for input media
  content_video=args.media[0]
  if args.verbose: nprint('content_video: ',content_video)
  content_dir=path.dirname(content_video)
  if args.verbose: print('content_dir: ',content_dir)
  content_filename=path.basename(content_video)
  if args.verbose: print('content_filename: ',content_filename)
  content_filename_parts=path.splitext(content_filename)
  content_filename_base=content_filename_parts[0]
  if args.verbose: print('content_filename_base: ',content_filename_base)
  extension=content_filename_parts[1][1:]
  if args.verbose: print('extension: ',extension)
  if args.verbose: nprint('')
  
  args.content_video = content_video
  args.content_dir = content_dir
  args.content_filename = content_filename
  args.content_extension = extension
  if not args.output_extension: args.output_extension = extension
  args.content_filename_base = content_filename_base
  
  style_images_filenames = []
  style_dir = False
  style_images = args.media[1:]
  
  style_nickname=""
  if args.verbose: print('style_images:',style_images)
  if args.skipflow:
    style_images.pop()
  if args.skiprender:
    style_images.pop()
  for style_image in style_images:
    if args.verbose: nprint('style_image: ',style_image)
    # style_dir=$(dirname "$style_image")
    this_style_dir=path.dirname(style_image)
    if args.verbose: print('style_dir: ',this_style_dir)
    if style_dir is not False and this_style_dir != style_dir:
      eprint('Error! If using multiple styles they must reside in the same directory')
      die()
    style_dir = this_style_dir
    # style_filename=$(basename "$style_image")
    style_filename=path.basename(style_image)
    style_images_filenames.append(style_filename)
    if args.verbose: print('style_filename: ',style_filename)
    style_filename_parts=path.splitext(style_filename)
    style_filename_base=style_filename_parts[0]
    style_nickname+="_"+style_filename_base
    if args.verbose: print('style_filename_base: ',style_filename_base)
    if args.verbose: nprint('')
  
  args.style_dir = style_dir
  args.style_nickname = style_nickname
  args.style_images_filenames = style_images_filenames
  if args.verbose: print('style_nickname: ',style_nickname)
  if args.verbose: print('style_images_filenames: ',style_nickname)
  
  #auto-calculate style_imgs_weights if not given for multi-style image
  if len(args.style_images_filenames) and len(args.style_imgs_weights) != len(args.style_images_filenames):
    new_weights = []
    amnt = len(args.style_images_filenames)
    average_weight = 1/amnt
    for i in range(amnt): new_weights.append(str(average_weight))
    args.style_imgs_weights = new_weights
  else:
    new_weights = []
    for w in args.style_imgs_weights: new_weights.append(str(w))
    args.style_imgs_weights = new_weights
    
  
  print('style_imgs_weights:', args.style_imgs_weights)
  
  if args.verbose: nprint('Done parsing args')

  return args


def nprint(*str):
  print('\n'+" ".join(str))
  

def eprint(*str):
  print(colored(" ".join(str), 'red') )

def die(*str):
  print(colored("bye bye", 'red') )
  sys.exit(1)
  
def prog_exists(name):
  return which(name) is not None

def tight_crc32(_data):
  try:
    data = json.dumps(_data)
  except:
    data = _data
  return (format(zlib.crc32(data.encode('utf8')), 'x'))

def prepare_input(args):
  if args.verbose: cprint('# prepare_input','cyan')
  
  if args.verbose: nprint('Checking if ffmpeg installed..')
  # Find out whether ffmpeg or avconv is installed on the system
  FFMPEG="ffmpeg"
  if(prog_exists(FFMPEG) is False):
    FFMPEG="avconv"
    if args.verbose: print('ffmpeg not found. Checking alternative avconv..')
    if(prog_exists(FFMPEG) is False):
      if args.verbose: print('avconv not found.')
      print("Error! This script requires either ffmpeg or avconv installed.  Aborting.")
      sys.exit(1)
    else:
      if args.verbose: cprint('avconv found!','green')
  else:
    if args.verbose: cprint('ffmpeg found!','green')
  
  args.FFMPEG = FFMPEG
  
  if args.verbose: nprint('')
  


  # Determine max size
  processParts = ('ffprobe -v error -of flat=s=_ -select_streams v:0 -show_entries stream=width,height '+args.content_video).split()
  process = subprocess.Popen(processParts,
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE,
                           stdin=subprocess.PIPE,
                           universal_newlines=True)
  ffprobe_details, err = process.communicate()
  width = re.search('streams_stream_0_width=([0-9]+)', ffprobe_details).group(1)
  height = re.search('streams_stream_0_height=([0-9]+)', ffprobe_details).group(1)
  if args.max_size:
    max_size_arg=True
  else:
    max_size_arg=False
    args.max_size = max(width,height)

  
  content_base_sized = args.content_filename_base+'_ms'+str(args.max_size)
  args.content_base_sized = content_base_sized
  
  # Prepare temp dir
  temp_dir = "./video_input/"+content_base_sized
  pathlib.Path(temp_dir).mkdir(parents=True, exist_ok=True)
  args.temp_dir = temp_dir


  # Prepare output dir
  hashableargs = ['additional_args','interlaced','style_imgs_weights']
  hashargs = {}
  for arg in hashableargs:
    hashargs[arg] = getattr(args,arg)
  argshash = tight_crc32(hashargs)
  if args.verbose: print('hashableargs',hashableargs)
  if args.verbose: print('hashargs',hashargs)
  if args.verbose: print('argshash',argshash)
  out_dir_name=args.content_filename_base+"_ms"+str(args.max_size)+"-x-"+args.style_nickname+"_"+argshash
  if len(out_dir_name) > args.max_output_dir_name_length:
    out_dir_name=args.content_filename_base+"_ms"+str(args.max_size)+"-x-"+tight_crc32(args.style_nickname)+"_"+argshash
     #we assume hashing the styles will minimize the length enough
     
  if len(out_dir_name) > args.max_output_dir_name_length:
    eprint('Unable to shorten output directory name to within desired limits!')
    eprint('Dir name length:'+ str(len(out_dir_name)) + ' > Max length:' + str(args.max_output_dir_name_length))
    die()
    
  args.out_dir = path.join("./video_output/",out_dir_name)
  out_dir_etc = path.join(args.out_dir,'etc')
  pathlib.Path(out_dir_etc).mkdir(parents=True, exist_ok=True)
  if args.verbose: print('out_dir: ',args.out_dir)
     



  
  if args.verbose: print('max_size_arg:',max_size_arg)
  if args.verbose: print('args.max_size:',args.max_size)



  # Save frames of the video as individual image files
  nprint(colored('Saving frames of the video as individual image files','yellow'))
  if not path.exists(temp_dir+'/frame_0001.ppm'):
    
    ffmpeg_filters="scale=iw*sar:ih" #fix aspect ratio
    if args.interlaced:
      ffmpeg_filters=ffmpeg_filters+',yadif'
    
    if max_size_arg:
      if width > height:
        processParts = [FFMPEG,'-i', args.content_video, '-vf', ffmpeg_filters+",scale="+str(args.max_size)+":-1", temp_dir+'/frame_%04d.ppm']
      else:
        processParts = [FFMPEG, '-i', args.content_video, '-vf', ffmpeg_filters+',scale=-1:'+str(args.max_size), temp_dir+'/frame_%04d.ppm']
    else:
      processParts = [FFMPEG, '-i', args.content_video, '-vf', ffmpeg_filters, temp_dir+'/frame_%04d.ppm']
        
    
    try:
      process = subprocess.Popen(processParts, stdin=subprocess.PIPE, universal_newlines=True)
      process.communicate()
    except KeyboardInterrupt:
      process.terminate()
      die()
  
  
  num_frames = len(glob.glob(path.join(temp_dir,'*.ppm')))
  
  
  if args.verbose: print('width:',width)
  if args.verbose: print('height:',height)
  if args.verbose: print('max_size:',args.max_size)
  if args.verbose: print('num_frames:',num_frames)
  
  args.num_frames = num_frames
  if not args.end_frame: args.end_frame = num_frames
  

def save_rawargs(args):
  f = open(path.join(args.out_dir,'etc','rawargs.txt'), "w")
  f.write(" ".join(sys.argv))
  f.close()
  
def save_neural_style_args(args,ns_argslist):
  f = open(path.join(args.out_dir,'etc','rawargs.txt'), "w")
  f.write(" ".join(ns_argslist))
  f.close()

def optical_flow(args):
  if args.verbose: cprint('optical_flow','cyan')
  if args.skipflow:
    nprint(colored('Skipping optical flow..','yellow'))
  else:
    print("Computing optical flow [CPU]. This will take a while...")
    os.chdir('./video_input')
    processParts = ['bash','make-opt-flow.sh', args.content_base_sized+'/frame_%04d.ppm', args.content_base_sized]
    if args.verbose: nprint(" ".join(processParts))
    # process = subprocess.Popen(processParts,
                             # stdout=subprocess.PIPE,
                             # universal_newlines=True)
    # read_process(process)
    
    try:
      process = subprocess.Popen(processParts, stdin=subprocess.PIPE, universal_newlines=True)
      process.communicate()
    except KeyboardInterrupt:
      process.terminate()
      die()
    os.chdir('..')


def read_process(process):
  while True:
    output = process.stdout.readline()
    print(output.strip())
    # Do something else
    return_code = process.poll()
    if return_code is not None:
      print('RETURN CODE', return_code)
      # Process has finished, read rest of the output 
      for output in process.stdout.readlines():
        print(output.strip())
      break
      
def stylize_video(args):
  if args.verbose: nprint(colored('stylize_video','cyan'))
  if args.skiprender:
    nprint(colored('Skipping stylization render pass..','yellow'))
  else:
    if args.verbose: nprint(colored('Rendering stylized video frames [CPU & GPU]. This will take a while...','cyan'))
    processParts = [
      # 'python',
      sys.executable,
      'neural_style.py', '--video', 
      '--optical_flow_dir', args.temp_dir, 
      '--video_input_dir', args.temp_dir, 
      '--video_output_dir', args.out_dir, 
      '--device', '/gpu:'+str(args.gpu),
      '--style_imgs_dir', args.style_dir, 
      '--style_imgs'] + args.style_images_filenames + [
      '--end_frame', str(args.end_frame), 
      '--max_size', str(args.max_size), 
      '--verbose', 
      '--style_imgs_weights' ] + args.style_imgs_weights + args.additional_args
    
    print(" ".join(processParts))
                   
    save_neural_style_args(args,processParts)
                      
    try:
      process = subprocess.Popen(processParts,
                               # stderr=subprocess.PIPE,
                               stdin=subprocess.PIPE,
                               universal_newlines=True)
      res, err = process.communicate()
      # if err: # warnings are sent to stderr and so cannot be trusted as signal of failure
        # cprint('ERROR:','red')
        # print(colored(err,'yellow'))
        # die()
    except KeyboardInterrupt:
      process.terminate()
      # process.send_signal(signal.SIGINT)
      # process.wait()
      die()
      
    # check if render process hasn't completed expected amount of work
    content_frame_frmt = 'frame_{}.ppm'
    if not path.exists(path.join(args.out_dir, content_frame_frmt.format(str(args.end_frame).zfill(4)))):
      cprint('ERROR:','red')
      cprint('Cannot find end frame in video output directory. Render process ended early?','yellow')
      die()
      
                    
    combine_frames(args)         

      
def combine_frames(args):
  # Create video from output images.
  print( "Converting image sequence to video.  This should be quick..." )
  stylied_video_out_path = (path.join(args.out_dir,"etc",args.content_base_sized+"-stylized."+args.output_extension))
  if path.exists(stylied_video_out_path) and not args.overwrite_image_sequence_video:
    print( "Image sequence previously converted. Skipping.." )
  else:
    processParts = (args.FFMPEG + " -v quiet -i "+(path.join(args.out_dir,"frame_%04d.ppm"))+" "+stylied_video_out_path+" -y").split()
    # print(" ".join(processParts))
    # process = subprocess.Popen(processParts,
                             # stdout=subprocess.PIPE,
                             # universal_newlines=True)
    # read_process(process)
    try:
      process = subprocess.Popen(processParts,
                               stdin=subprocess.PIPE,
                               universal_newlines=True)
      process.communicate()
    except KeyboardInterrupt:
      process.terminate()
      # process.send_signal(signal.SIGINT)
      # process.wait()
      die()


def main():
  global args
  args = parse_args()
  prepare_input(args)
  save_rawargs(args)
  optical_flow(args)
  stylize_video(args)
  nprint(colored("\nThe End!", 'yellow'))

if __name__ == '__main__':
  main()
